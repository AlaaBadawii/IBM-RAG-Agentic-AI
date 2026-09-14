import re

import gradio as gr
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models.utils.enums import DecodingMethods
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ibm import WatsonxEmbeddings, WatsonxLLM
from youtube_transcript_api import YouTubeTranscriptApi

# ============================================================
# Configuration
# ============================================================

# MODEL_ID = "ibm/granite-4-h-small"

WATSONX_URL = "https://us-south.ml.cloud.ibm.com"

MODEL_ID = "ibm/granite-4-h-small"

EMBEDDING_MODEL_ID = "ibm/granite-embedding-278m-multilingual"

# This is the project used by your Skills Network environment.
PROJECT_ID = "skills-network"

# EMBEDDING_MODEL_ID = "ibm/slate-30m-english-rtrvr-v2"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

RETRIEVAL_K = 5

SUMMARY_CHUNK_SIZE = 5000
SUMMARY_CHUNK_OVERLAP = 200


# ============================================================
# Global application resources
# ============================================================

credentials = None
llm = None
embedding_model = None


def initialize_resources():
    """
    Initialize Watsonx credentials, LLM, and embedding model once.
    """

    global credentials
    global llm
    global embedding_model

    if credentials is not None and llm is not None and embedding_model is not None:
        return

    # --------------------------------------------------------
    # Credentials
    # --------------------------------------------------------

    credentials = Credentials(url=WATSONX_URL)

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

    parameters = {
        GenParams.DECODING_METHOD: DecodingMethods.GREEDY,
        GenParams.MAX_NEW_TOKENS: 900,
    }

    llm = WatsonxLLM(
        model_id=MODEL_ID,
        url=credentials.get("url"),
        project_id=PROJECT_ID,
        params=parameters,
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    embedding_model = WatsonxEmbeddings(
        model_id=EMBEDDING_MODEL_ID,
        url=credentials.get("url"),
        project_id=PROJECT_ID,
    )


# ============================================================
# YouTube utilities
# ============================================================


def get_video_id(url):
    """
    Extract the YouTube video ID from common YouTube URL formats.
    """

    if not url:
        return None

    url = url.strip()

    patterns = [
        # https://www.youtube.com/watch?v=dQw4w9WgXcQ
        r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
        # https://youtu.be/dQw4w9WgXcQ
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        # https://www.youtube.com/embed/dQw4w9WgXcQ
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        # https://www.youtube.com/shorts/dQw4w9WgXcQ
        r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def get_transcript(url):
    """
    Fetch an English YouTube transcript.

    Preference:
        1. Manually created English transcript
        2. Auto-generated English transcript

    Returns:
        FetchedTranscript or None
    """

    video_id = get_video_id(url)

    if not video_id:
        raise ValueError(
            "Invalid YouTube URL. Please provide a valid YouTube video URL."
        )

    try:
        api = YouTubeTranscriptApi()

        transcript_list = api.list(video_id)

        generated_transcript = None

        for transcript in transcript_list:
            if transcript.language_code != "en":
                continue

            fetched = transcript.fetch()

            # Prefer manually created transcript.
            if not transcript.is_generated:
                return fetched

            # Keep generated transcript as fallback.
            if generated_transcript is None:
                generated_transcript = fetched

        return generated_transcript

    except Exception as exc:
        raise RuntimeError(f"Could not retrieve the YouTube transcript: {exc}") from exc


# ============================================================
# Transcript processing
# ============================================================


def process(transcript):
    """
    Convert a FetchedTranscript into a plain text representation.

    Example:

        Text: Hello everyone.
        Start: 0.0

    """

    if transcript is None:
        return ""

    lines = []

    for snippet in transcript:
        try:
            text = snippet.text.strip()
            start = snippet.start

            if text:
                lines.append(f"Text: {text} Start: {start:.2f}")

        except (AttributeError, KeyError, TypeError):
            # Ignore malformed transcript entries.
            continue

    return "\n".join(lines)


def clean_transcript(processed_transcript):
    """
    Remove unnecessary whitespace from the transcript.
    """

    if not processed_transcript:
        return ""

    lines = []

    for line in processed_transcript.splitlines():
        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def chunk_transcript(
    processed_transcript,
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
):
    """
    Split transcript into chunks suitable for embeddings/RAG.
    """

    if not processed_transcript:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return text_splitter.split_text(processed_transcript)


# ============================================================
# FAISS
# ============================================================


def create_faiss_index(chunks):
    """
    Create a FAISS vector store from transcript chunks.
    """

    if not chunks:
        raise ValueError("No transcript chunks were created.")

    initialize_resources()

    return FAISS.from_texts(
        chunks,
        embedding_model,
    )


def retrieve(faiss_index, query, k=RETRIEVAL_K):
    """
    Retrieve the most relevant transcript chunks.
    """

    if faiss_index is None:
        return []

    if not query or not query.strip():
        return []

    return faiss_index.similarity_search(
        query,
        k=k,
    )


# ============================================================
# LLM helpers
# ============================================================


def call_llm(prompt):
    """
    Invoke Watsonx LLM and normalize the response.
    """

    initialize_resources()

    response = llm.invoke(prompt)

    if isinstance(response, str):
        return response.strip()

    return str(response).strip()


# ============================================================
# Summarization
# ============================================================

SUMMARY_PROMPT = PromptTemplate(
    input_variables=["transcript"],
    template="""
You are an AI assistant that summarizes YouTube video transcripts.

Summarize the transcript below.

Requirements:
- Capture the main ideas and important details.
- Do not invent information.
- Ignore timestamps.
- Do not mention that you are summarizing a transcript.
- Keep the summary concise but informative.
- Write in clear paragraphs.
- Focus only on information contained in the transcript.

Transcript:

{transcript}

Summary:
""",
)


def summarize_chunk(chunk):
    """
    Summarize one transcript chunk.
    """

    prompt = SUMMARY_PROMPT.format(transcript=chunk)

    return call_llm(prompt)


def summarize_video(video_url):
    """
    Fetch transcript and generate a summary.

    Large transcripts are summarized chunk-by-chunk first,
    then the partial summaries are combined.
    """

    if not video_url or not video_url.strip():
        return ("Please provide a valid YouTube URL.", "No URL provided.")

    try:
        transcript = get_transcript(video_url)

        if transcript is None:
            return (
                "No English transcript is available for this video.",
                "Transcript not available.",
            )

        processed = process(transcript)

        processed = clean_transcript(processed)

        if not processed:
            return (
                "The transcript was retrieved but contains no usable text.",
                "Transcript was empty.",
            )

        chunks = chunk_transcript(
            processed,
            chunk_size=SUMMARY_CHUNK_SIZE,
            chunk_overlap=SUMMARY_CHUNK_OVERLAP,
        )

        if not chunks:
            return ("Could not create transcript chunks.", "Chunking failed.")

        partial_summaries = []

        for index, chunk in enumerate(chunks, start=1):
            summary = summarize_chunk(chunk)

            if summary:
                partial_summaries.append(f"Part {index}:\n{summary}")

        if not partial_summaries:
            return ("The model did not return a summary.", "Summarization failed.")

        # If there is only one chunk, there is no need for
        # another LLM request.
        if len(partial_summaries) == 1:
            return (
                partial_summaries[0].replace("Part 1:\n", ""),
                "Transcript fetched and summarized successfully.",
            )

        # ----------------------------------------------------
        # Combine partial summaries.
        # ----------------------------------------------------

        combined_summaries = "\n\n".join(partial_summaries)

        final_prompt = f"""
You are an AI assistant creating a final summary of a YouTube video.

Below are summaries of different parts of the same video.

Create one coherent final summary.

Requirements:
- Combine the important information.
- Remove repetition.
- Do not invent information.
- Do not mention the intermediate summaries.
- Do not include timestamps.
- Keep the result concise and informative.

Partial summaries:

{combined_summaries}

Final summary:
"""

        final_summary = call_llm(final_prompt)

        return (final_summary, "Transcript fetched and summarized successfully.")

    except Exception as exc:
        return (f"Error: {exc}", "Failed to process the video.")


# ============================================================
# Question Answering
# ============================================================

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are an expert assistant answering questions about a YouTube video.

Use ONLY the information contained in the provided video context.

Requirements:
- Answer the user's question directly.
- Do not invent facts.
- Do not use outside knowledge.
- If the context does not contain enough information to answer,
  clearly say that the answer cannot be determined from the video.
- Be concise but sufficiently detailed.
- Do not repeat the question.

Video context:

{context}

Question:

{question}

Answer:
""",
)


def format_documents(documents):
    """
    Convert retrieved LangChain Documents into plain context.
    """

    if not documents:
        return ""

    return "\n\n---\n\n".join(document.page_content for document in documents)


def answer_question(video_url, user_question):
    """
    Answer a question about a YouTube video using RAG.
    """

    if not video_url or not video_url.strip():
        return "Please provide a valid YouTube URL."

    if not user_question or not user_question.strip():
        return "Please enter a question."

    try:
        # ----------------------------------------------------
        # Fetch transcript
        # ----------------------------------------------------

        transcript = get_transcript(video_url)

        if transcript is None:
            return "No English transcript is available for this video."

        processed = process(transcript)

        processed = clean_transcript(processed)

        if not processed:
            return "The transcript contains no usable text."

        # ----------------------------------------------------
        # Chunk transcript
        # ----------------------------------------------------

        chunks = chunk_transcript(
            processed,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        if not chunks:
            return "Could not create transcript chunks."

        # ----------------------------------------------------
        # Create FAISS index
        # ----------------------------------------------------

        faiss_index = create_faiss_index(chunks)

        # ----------------------------------------------------
        # Retrieve relevant context
        # ----------------------------------------------------

        documents = retrieve(
            faiss_index,
            user_question,
            k=min(RETRIEVAL_K, len(chunks)),
        )

        if not documents:
            return (
                "I could not find relevant information in the video for this question."
            )

        context = format_documents(documents)

        # ----------------------------------------------------
        # Generate answer
        # ----------------------------------------------------

        prompt = QA_PROMPT.format(
            context=context,
            question=user_question,
        )

        answer = call_llm(prompt)

        return answer

    except Exception as exc:
        return f"Error: {exc}"


# ============================================================
# Gradio UI
# ============================================================


def build_interface():

    with gr.Blocks() as interface:
        gr.Markdown(
            """
            # YouTube Video Summarizer and Q&A

            Enter a YouTube video URL to summarize the video
            or ask questions about its transcript.
            """
        )

        video_url = gr.Textbox(
            label="YouTube Video URL",
            placeholder=("https://www.youtube.com/watch?v=..."),
        )

        with gr.Row():
            summarize_btn = gr.Button(
                "Summarize Video",
                variant="primary",
            )

            question_btn = gr.Button(
                "Ask a Question",
            )

        summary_output = gr.Textbox(
            label="Video Summary",
            lines=8,
        )

        question_input = gr.Textbox(
            label="Ask a Question About the Video",
            placeholder=("What are the main ideas discussed in the video?"),
        )

        answer_output = gr.Textbox(
            label="Answer to Your Question",
            lines=8,
        )

        transcript_status = gr.Textbox(
            label="Transcript Status",
            interactive=False,
        )

        # ----------------------------------------------------
        # Events
        # ----------------------------------------------------

        summarize_btn.click(
            fn=summarize_video,
            inputs=video_url,
            outputs=[
                summary_output,
                transcript_status,
            ],
        )

        question_btn.click(
            fn=answer_question,
            inputs=[
                video_url,
                question_input,
            ],
            outputs=answer_output,
        )

    return interface


# ============================================================
# Application entry point
# ============================================================

if __name__ == "__main__":
    interface = build_interface()

    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
    )
