import hashlib
import os
from pathlib import Path
from typing import Any, Sequence

import gradio as gr
from gradio.themes import Citrus

from agents.workflow import AgentWorkflow
from config import constants
from document_processor.file_handler import DocumentProcessor
from retriever.builder import RetrieverBuilder
from utils.logging import logger


# 1. Example questions and their associated documents.
EXAMPLES = {
    "Google 2024 Environmental Report": {
        "question": (
            "Retrieve the data center PUE efficiency values in Singapore "
            "2nd facility in 2019 and 2022. Also retrieve regional average "
            "CFE in Asia pacific in 2023"
        ),
        "file_paths": ["examples/google-2024-environmental-report.pdf"],
    },
    "DeepSeek-R1 Technical Report": {
        "question": (
            "Summarize DeepSeek-R1 model's performance evaluation on all "
            "coding tasks against OpenAI o1-mini model"
        ),
        "file_paths": ["examples/DeepSeek Technical Report.pdf"],
    },
}


def _get_file_path(uploaded_file: Any) -> str:
    """Resolve a Gradio file value to its local filesystem path."""
    if isinstance(uploaded_file, (str, os.PathLike)):
        return os.fspath(uploaded_file)

    # Support file objects that expose their path through .name or .path.
    for attribute in ("name", "path"):
        file_path = getattr(uploaded_file, attribute, None)

        if isinstance(file_path, (str, os.PathLike)):
            return os.fspath(file_path)

    raise TypeError(f"Unsupported uploaded-file value: {type(uploaded_file).__name__}")


def _get_file_hashes(uploaded_files: Sequence[Any]) -> tuple[tuple[str, str], ...]:
    """
    Generate a SHA-256 signature for the selected files.

    The filename is included so that renaming a document invalidates the
    cache when its source metadata may need to change.
    """
    signatures = []

    for uploaded_file in uploaded_files:
        file_path = Path(_get_file_path(uploaded_file))

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Uploaded file is no longer available: {file_path.name}"
            )

        digest = hashlib.sha256()

        # Read in blocks instead of loading the entire file into memory.
        with file_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)

        signatures.append((file_path.name, digest.hexdigest()))

    # Sorting makes the signature independent of upload order.
    # A tuple also preserves repeated files, unlike a set.
    return tuple(sorted(signatures))


def main():
    # Initialize the lab components.
    processor = DocumentProcessor()
    retriever_builder = RetrieverBuilder()
    workflow = AgentWorkflow()

    # Custom CSS.
    css = """
    .title {
        font-size: 1.5em !important;
        text-align: center !important;
        color: #FFD700;
    }

    .subtitle {
        font-size: 1em !important;
        text-align: center !important;
        color: #FFD700;
    }

    .text {
        text-align: center;
    }
    """

    # Welcome animation, executed when the Gradio page loads.
    js = """
    () => {
        const gradioContainer = document.querySelector(".gradio-container");

        if (
            !gradioContainer ||
            document.getElementById("gradio-animation")
        ) {
            return;
        }

        const container = document.createElement("div");
        container.id = "gradio-animation";
        container.style.fontSize = "2em";
        container.style.fontWeight = "bold";
        container.style.textAlign = "center";
        container.style.marginBottom = "20px";
        container.style.color = "#eba93f";

        gradioContainer.insertBefore(
            container,
            gradioContainer.firstChild
        );

        const text = "Welcome to DocChat 🐥!";

        for (let i = 0; i < text.length; i++) {
            setTimeout(() => {
                const letter = document.createElement("span");
                letter.style.opacity = "0";
                letter.style.transition = "opacity 0.1s";
                letter.textContent = text[i];

                container.appendChild(letter);

                setTimeout(() => {
                    letter.style.opacity = "0.9";
                }, 50);
            }, i * 250);
        }
    }
    """

    with gr.Blocks(
        theme=Citrus(),
        title="DocChat 🐥",
        css=css,
        js=js,
    ) as demo:
        # 2. Introduction.
        gr.Markdown(
            "## DocChat: powered by Docling 🐥 and LangGraph",
            elem_classes="subtitle",
        )

        gr.Markdown(
            "# How it works ✨:",
            elem_classes="title",
        )

        gr.Markdown(
            "📤 Upload your document(s), enter your query, then press Submit 📝",
            elem_classes="text",
        )

        gr.Markdown(
            "Or select an example from the dropdown, press "
            "Load Example, and then press Submit 📝",
            elem_classes="text",
        )

        gr.Markdown(
            "⚠️ Supported formats: PDF, DOCX, TXT, and Markdown.",
            elem_classes="text",
        )

        # 3. Per-session state for document caching.
        session_state = gr.State(
            {
                "file_hashes": tuple(),
                "retriever": None,
            }
        )

        # 4. Layout.
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Example 📂")

                example_dropdown = gr.Dropdown(
                    label="Select an Example 🐥",
                    choices=list(EXAMPLES.keys()),
                    value=None,
                )

                load_example_btn = gr.Button("Load Example 🛠️")

                files = gr.Files(
                    label="📄 Upload Documents",
                    file_types=constants.ALLOWED_TYPES,
                    type="filepath",
                )

                question = gr.Textbox(
                    label="❓ Question",
                    lines=3,
                )

                submit_btn = gr.Button("Submit 🚀")

            with gr.Column():
                answer_output = gr.Textbox(
                    label="🐥 Answer",
                    interactive=False,
                )

                verification_output = gr.Textbox(
                    label="✅ Verification Report",
                    interactive=False,
                )

        # 5. Load an example into the UI.
        def load_example(example_key: str | None):
            """Load the selected example's question and local files."""
            if not example_key or example_key not in EXAMPLES:
                return [], ""

            example_data = EXAMPLES[example_key]
            example_question = example_data["question"]
            loaded_files = []

            for path in example_data["file_paths"]:
                if Path(path).is_file():
                    loaded_files.append(path)
                else:
                    logger.warning("Example file not found: %s", path)

            if not loaded_files:
                logger.warning(
                    "No files were found for example: %s",
                    example_key,
                )

            return loaded_files, example_question

        load_example_btn.click(
            fn=load_example,
            inputs=[example_dropdown],
            outputs=[files, question],
        )

        # 6. Process a submitted question.
        def process_question(
            question_text: str,
            uploaded_files: Sequence[Any] | None,
            state: dict[str, Any] | None,
        ):
            """Process documents, reuse retrieval state, and run the agents."""
            state = dict(state or {})
            state.setdefault("file_hashes", tuple())
            state.setdefault("retriever", None)

            try:
                if not question_text or not question_text.strip():
                    raise ValueError("❌ Question cannot be empty.")

                if not uploaded_files:
                    raise ValueError("❌ No documents uploaded.")

                # Determine whether the selected documents have changed.
                current_hashes = _get_file_hashes(uploaded_files)

                if state["retriever"] is None or current_hashes != state["file_hashes"]:
                    logger.info("Processing new or changed documents...")

                    chunks = processor.process(list(uploaded_files))

                    if not chunks:
                        raise ValueError(
                            "No readable text could be extracted "
                            "from the selected documents."
                        )

                    retriever = retriever_builder.build_hybrid_retriever(chunks)

                    # Update the cache only after building succeeds.
                    state["file_hashes"] = current_hashes
                    state["retriever"] = retriever

                    logger.info("Document processing and retriever creation completed.")
                else:
                    logger.info(
                        "Reusing the existing retriever for unchanged documents."
                    )

                # Run the existing multi-agent workflow.
                result = workflow.full_pipeline(
                    question=question_text.strip(),
                    retriever=state["retriever"],
                )

                return (
                    result["draft_answer"],
                    result["verification_report"],
                    state,
                )

            except Exception as exc:
                logger.exception("Question processing failed.")

                return (
                    f"❌ Error: {exc}",
                    "",
                    state,
                )

        submit_btn.click(
            fn=process_question,
            inputs=[question, files, session_state],
            outputs=[
                answer_output,
                verification_output,
                session_state,
            ],
        )

    # Keep the application local by default.
    demo.launch(
        server_name="127.0.0.1",
        server_port=5000,
        share=False,
    )


if __name__ == "__main__":
    main()
