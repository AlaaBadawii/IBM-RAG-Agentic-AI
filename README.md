# IBM RAG and Agentic AI Professional Certificate

> Hands-on engineering portfolio for IBM's RAG and Agentic AI Professional Certificate: guided labs, local rebuilds, independent extensions, and retained plans/notebooks spanning RAG, multimodal apps, LangGraph, CrewAI, AG2, and BeeAI. Implementations use a mix of OpenRouter, local Hugging Face models, IBM watsonx.ai, and Gemini-backed BeeAI examples.

**Progress as of November 9, 2026: Courses 1–8 completed · Course 9 next · Course 10 not started.** Course completion and project maturity are reported separately.

[Courses and projects](#courses-and-projects) · [Technical skills](#technical-skills-demonstrated) · [Related repositories](#related-repositories) · [Structure](#repository-structure) · [Setup](#setup) · [Next steps](#progress--next-steps)

---

## About the Program

**[IBM RAG and Agentic AI Professional Certificate](https://www.coursera.org/professional-certificates/ibm-rag-and-agentic-ai)** — a 10-course Professional Certificate offered by **IBM on Coursera**, with teaching by IBM Skills Network.

> Build real-world AI with RAG and agentic AI. Use AI tools to streamline automation, drive innovation & take your career further, faster.

**Listed instructors include:** IBM Skills Network Team, Wojciech 'Victor' Fulmyk, and Ricky Shi. The official program page provides the full instructor roster.

**Program:** Advanced level · Python/web-development background expected · Flexible schedule. The official course estimates below total **103 hours**; they describe the syllabus, not time spent on these independent builds. Titles and durations were checked against the program page on November 9, 2026.

| # | Official course title / local landing page | Duration | Course focus | Progress |
|---|---|---:|---|---|
| 1 | [Develop Generative AI Applications: Get Started](Develop_Generative_AI_Applications_Get_Started/README.md) | 10 hours | Prompt engineering, LangChain, structured JSON, Flask, model comparison | **Completed** |
| 2 | [Build RAG Applications: Get Started](Build_RAG_Applications_Get_Started/README.md) | 7 hours | RAG pipelines, LangChain/LlamaIndex, Gradio interfaces | **Completed** |
| 3 | [Vector Databases for RAG: An Introduction](Vector_Databases_for_RAG_An_Introduction/README.md) | 9 hours | ChromaDB operations, embeddings, similarity search, recommendation | **Completed** |
| 4 | [Advanced RAG with Vector Databases and Retrievers](Advanced_RAG_with_Vector_Databases_and_Retrievers/README.md) | 8 hours | FAISS/Chroma, indexing concepts, advanced retrieval, Gradio RAG | **Completed** |
| 5 | [Build Multimodal Generative AI Applications](Build_Multimodal_Generative_AI_Applications/README.md) | 9 hours | Text/image/speech/video concepts and multimodal application workflows | **Completed** |
| 6 | [Fundamentals of Building AI Agents](Fundamentals_of_Building_AI_Agents/README.md) | 11 hours | Tool calling, agent loops, dataframe/visualization and SQL agents | **Completed** |
| 7 | [Agentic AI with LangChain and LangGraph](Agentic_AI_with_LangChain_and_LangGraph/README.md) | 11 hours | State, iteration, conditional logic, ReAct/Reflection/Reflexion, agentic RAG | **Completed** |
| 8 | [Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/README.md) | 14 hours | Workflow patterns, crews, AG2 conversations, BeeAI agents | **Completed** |
| 9 | Build AI Agents using MCP | 10 hours | MCP architecture, FastMCP servers/clients, transports, approval and secure workflows | **Next — not started** |
| 10 | RAG and Agentic AI Capstone Project | 14 hours | End-to-end data, multimodal retrieval, multi-agent and MCP integration | **Not started** |

---

## Repository at a Glance

| Course | Projects and retained labs | Important state distinctions |
|---|---|---|
| 1 | GenAI Flask App · AI Email Assistant · Book/Movie Advisor | Guided-project rebuild plus two practice extensions; JSON schemas guide output but do not independently validate returned dicts |
| 2 | Gradio demos · historical Icebreaker entry | Sentence builder implemented; image experiment needs a model-flow fix; Icebreaker is an unavailable gitlink; Personal Branding Agent is external |
| 3 | Books Advanced Search · Food Recommendation System · Employee Similarity Search · Job Matcher | Food has execution blockers; Job Matcher is plan-only |
| 4 | YouTube RAG Summarizer & QA | IBM-stack baseline implemented; provider-independent rebuild remains planned |
| 5 | Image Captioning · Vocabulary Storyteller · Personal Storyteller · Style Finder · Cal Coach · Meeting Assistant | API/container and dataset/runtime limitations; Meeting Assistant is instructions-only |
| 6 | Math Assistant · Data Analysis · Tool-Calling Agent · NL-to-SQL · Data Visualization Agent | Visualization is a notebook plus incomplete draft; Math agent startup/registration has limitations |
| 7 | Stateful Workflows · Reflection · Deep Research Reflexion · ReAct · DocChat Multi-Agent RAG | Implemented educational workflows, with explicit testing, retrieval, and termination caveats |
| 8 | Workflow Patterns · Orchestration & Evaluation · NourishBot · Research to Content · MealMind · AG2 Lab · BeeAI Lab | Guided implementations and experiments; MealMind's default runner and BeeAI's standalone factory demo are blocked |

There are **32 project/lab directories with regular tracked content**, plus the unavailable Icebreaker gitlink. Plans, stubs, experimental edges, and missing runtime inputs are labeled below and in project READMEs. The extracted Personal Branding Agent is maintained separately.

---

## Courses and Projects

### Course 1 — Develop Generative AI Applications: Get Started

**Course status: Completed.** The course covers LLM APIs, prompt templates, few-shot prompting, LangChain chains (LCEL), and structured output. The guided Flask app was rebuilt with OpenRouter, followed by two independent practice extensions.

See [`Develop_Generative_AI_Applications_Get_Started/README.md`](Develop_Generative_AI_Applications_Get_Started/README.md).

#### [GenAI Flask App](Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App/README.md)

Type a message, pick one of three configured models (Llama / DeepSeek R1 / Mistral), and receive parsed JSON (`summary`, `sentiment`, `response`). The legacy `granite` slot actually selects `deepseek/deepseek-r1`. A shared `ChatPromptTemplate` + `JsonOutputParser` supplies schema-guided output, without separate Pydantic validation. Includes the live-API sanity check `llm_test.py`.

**Status:** Implemented guided-project rebuild · **Technologies:** Flask, LangChain LCEL, Pydantic schemas, OpenRouter · **Engineering focus:** prompt templates, structured output, provider abstraction.

#### [AI Email Assistant](Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant/README.md)

Generates polished emails (subject + body + improvement suggestions) as structured JSON. Adds a **Compare All** mode that runs the same prompt across four models in parallel and shows per-model latency, length, and a subject-quality score. The build log in `plan.md` documents real bugs (wrong OpenRouter base URL causing DNS failures, intermittent `OutputParserException` on markdown-wrapped JSON, langchain version drift).

**Status:** Implemented independent extension · **Technologies:** Flask, LangChain LCEL, Pydantic schemas, OpenRouter, vanilla JS (`Promise.all`) · **Engineering focus:** parallel browser fan-out, heuristic model comparison, escaped text rendering.

#### [Book/Movie Advisor](Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor/README.md)

Free-text mood → a requested three-card recommendation list, guided by nested Pydantic schemas. There are nine configured OpenRouter models and a separately maintained dropdown. Count and score bounds are prompt expectations, not independently enforced; mood-match scores are generated by the LLM, not embeddings.

**Status:** Implemented independent extension · **Technologies:** Flask, LangChain, Pydantic schemas, OpenRouter · **Engineering focus:** nested output formats, few-shot examples, model/configuration consistency.

**Key things learned (Course 1)**

- LCEL pipe chains: `prompt | llm | parser` is a runnable, testable unit.
- Structured output: a Pydantic schema can guide JSON generation; parsing a dict is not the same as validating it.
- Prompt engineering: input vs. partial variables, few-shot examples, JSON-literal escaping (`{{ }}`).
- Debugging order: key present → provider reachable → chain direct call → Flask → UI.

---

### Course 2 — Build RAG Applications: Get Started

**Course status: Completed.** IBM's course introduces RAG — document loading, chunking, embeddings, vector stores, retrieval, similarity search, query engines — taught through LlamaIndex and Gradio.

See [`Build_RAG_Applications_Get_Started/README.md`](Build_RAG_Applications_Get_Started/README.md).

#### LinkedIn Icebreaker Bot — unavailable gitlink

Historical entry for the course's Icebreaker RAG exercise. Git records mode `160000` at commit `9b8a9da7b0381686874d71740e74c72a71b7f74f`, with no tracked `.gitmodules` and no available referenced commit in the parent repo. A fresh clone does not supply runnable source. Local untracked files are not evidence of GitHub-visible implementation, commands, ports, or API configuration. See the [Course 2 availability note](Build_RAG_Applications_Get_Started/README.md#icebreaker-availability).

#### [Personal Branding Agent — extracted repository](https://github.com/AlaaBadawii/PersonalBrandingAgent)

This independent Course 2 extension grew into **Abu Prompt**, an evidence-grounded LinkedIn content-generation and publishing agent. It demonstrated curated knowledge, hybrid retrieval, deterministic verification, duplicate-aware publishing, and operational state. It was extracted from this repo; its source, setup, tests, current status, and remaining work are documented in the standalone repository.

#### [Gradio Demos](Build_RAG_Applications_Get_Started/Gradio/README.md)

A deterministic `gr.Interface` sentence builder and an experimental BLIP image script. The image script mixes a caption-generation model with ImageNet classification-style output and needs a code correction.

**Status:** Sentence builder implemented; image experiment incomplete · **Technologies:** Gradio, transformers, torch/torchvision · **Engineering focus:** component contracts, preprocessing, model-output compatibility.

**Key things learned (Course 2)**

- The RAG loop: load → split → embed → store → index → retrieve → generate.
- Chunking (`chunk_size`/`chunk_overlap`, sentence boundaries) is a design decision, not a default.
- `VectorStoreIndex`/`as_query_engine` hides retrieval; `as_retriever()` exposes it.
- Retrieval quality bounds generation quality; central provider factories reduce coupling, although some retained labs still have fixed configuration.

---

### Course 3 — Vector Databases for RAG: An Introduction

**Course status: Completed.** IBM's course teaches vector databases from the inside: embeddings, collections, CRUD, similarity search, distance metrics — with ChromaDB labs.

See [`Vector_Databases_for_RAG_An_Introduction/README.md`](Vector_Databases_for_RAG_An_Introduction/README.md).

#### [Books Advanced Search](Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search/README.md)

Modular app (data → documents → vector_store → repository → search) storing eight book records in persistent ChromaDB. Exercises cover similarity, genre/rating filtering, and combined search with idempotent upserts. Five functions in three test modules print results rather than asserting retrieval behavior.

**Status:** Implemented search exercises · **Technologies:** ChromaDB (`PersistentClient`), `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions) · **Engineering focus:** layered architecture, metadata filters, ingestion. The collection does not explicitly select cosine distance.

#### [Food Recommendation System](Vector_Databases_for_RAG_An_Introduction/Food_Recommendation_System/README.md)

Three-tier source progression over **185 tracked food records**: semantic CLI search → cuisine/calorie filters → watsonx RAG, plus budget/result-limit/comparison exercises. The scripts have dataset-path, metadata-key, missing-helper, and annotation blockers. The comparison's "RAG" response is Python formatting, not a live LLM call.

**Status:** Experimental implementation with execution blockers · **Technologies:** ChromaDB, `sentence-transformers`, `ibm-watsonx-ai` (`ibm/granite-4-h-small`) · **Engineering focus:** retrieval progression and consistent data contracts. No `LLM_*` environment variables are consumed.

#### [Similarity Search on Employee Records](Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records/README.md)

Single-file in-memory ChromaDB demo: 2 pure similarity searches, 3 metadata filters (department, experience, location), 1 combined query.

**Status:** Implemented guided lab · **Technologies:** ChromaDB, `sentence-transformers` · **Engineering focus:** `query()`/`get()`, explicitly configured cosine distance, metadata operators.

#### [Job Description Matcher](Vector_Databases_for_RAG_An_Introduction/job_description_matcher/README.md)

Proposal for semantic job search over ~30 descriptions, Hit@K/Precision@K evaluation, and an optional LCEL summary. No job dataset, search implementation, or CLI is tracked.

**Status:** Plan only (`plan.md`, `README.md`, `requirements.txt`; implementation not yet built) · **Technologies (planned):** ChromaDB, `sentence-transformers`.

**Key concepts practiced (Course 3)**

- ChromaDB collections: create, ingest, query, persist.
- Metadata filtering: `$in`, `$gte`, `$lte`, `$and`, `$or` inside `collection.query()`.
- Document construction: combining fields into effective searchable text.

---

### Course 4 — Advanced RAG with Vector Databases and Retrievers

**Course status: Completed.** Retained work centers on one project, with additional concepts studied in the course.

See the [Course 4 overview](Advanced_RAG_with_Vector_Databases_and_Retrievers/README.md).

#### [YouTube RAG Summarizer & QA](Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer/README.md)

YouTube URL → English transcript → two paths: hand-written chunked map-reduce-style summarization, or chunk → embed → FAISS → retrieve → grounded Q&A, served in Gradio `Blocks`. The single-file `ytbot.py` uses `ibm/granite-4-h-small` and `ibm/granite-embedding-278m-multilingual` with fixed Skills Network configuration. The provider-independent layered rebuild in `PLAN.md` is not implemented.

**Status:** Implemented IBM-stack lab baseline; rebuild planned · **Technologies:** Gradio, LangChain, FAISS, `langchain-ibm`, `youtube-transcript-api` · **Engineering focus:** separate summary/retrieval chunk budgets, transcript handling, grounded Q&A.

---

### Course 5 — Build Multimodal Generative AI Applications

**Course status: Completed.** Six entries include source implementations, independent text/audio extensions, experimental serving/runtime edges, and the instructions-only Meeting Assistant stub. See the [Course 5 overview](Build_Multimodal_Generative_AI_Applications/README.md).

#### [Image Captioning](Build_Multimodal_Generative_AI_Applications/Image_Captioning/README.md)

CLI/Gradio image→text service (caption, VQA, counting, assessment, extraction), with OpenRouter abstraction, retry/fallback, ADRs, and a [five-case qualitative dataset](Build_Multimodal_Generative_AI_Applications/Image_Captioning/evaluation/README.md). Seven unit modules and one mocked pipeline module contain 47 test functions. FastAPI upload routes currently pass filenames instead of uploaded bytes; container definitions exist but their build/default-command limitations are documented.

**Status:** Implemented CLI/Gradio; experimental API/container workflows · **Technologies:** FastAPI, Uvicorn, Gradio, OpenAI SDK/OpenRouter, Pillow, Docker definitions · **Engineering focus:** provider seams, resilience, upload contracts, qualitative evaluation.

#### [Vocab Learning App](Build_Multimodal_Generative_AI_Applications/Vocab_Learning_App/README.md)

Vocabulary list → programmatically validated definitions/examples/story (bounded retries) → one MP3 lesson in Gradio. Five test modules contain 77 test functions covering input, generation, validation, audio, and pipeline behavior with fakes.

**Status:** Implemented independent extension · **Technologies:** Gradio, OpenRouter-compatible chat API via `requests`, gTTS · **Engineering focus:** validated generation loops, TTS lesson assembly, deterministic pipeline tests.

#### [Personal Storyteller](Build_Multimodal_Generative_AI_Applications/Personal_Storyteller/README.md)

Topic-in → LLM educational story + MP3 narration via a minimal single-file Gradio app (OpenRouter-compatible endpoint, `meta-llama` default).

**Status:** Implemented minimal/experimental app · **Technologies:** Gradio, OpenRouter-compatible API, gTTS · **Engineering focus:** story generation + narration; fixed temporary audio path and no quality validation.

#### [Style Finder](Build_Multimodal_Generative_AI_Applications/Style_Finder/README.md)

Fashion-photo analyzer: matches uploads against precomputed outfit embeddings (ResNet50 + cosine similarity), then generates retail-style analysis with item/price/link via a Llama-4 vision model. Runs on the IBM watsonx stack.

**Status:** Implemented guided lab; external catalog dataset is not tracked · **Technologies:** Gradio, torch/torchvision (ResNet50), scikit-learn, `ibm-watsonx-ai`, pandas · **Engineering focus:** visual matching and catalog-grounded explanations. Fresh-clone execution needs that dataset and appropriate IBM runtime configuration.

#### [AI Nutrition Coach (`cal_coach_app`)](Build_Multimodal_Generative_AI_Applications/cal_coach_app/README.md)

Flask food-photo coach: base64-encodes uploads for a Llama-4 vision model and renders calorie/nutrient/health reports as HTML.

**Status:** Implemented guided lab with configuration/upload/error-path limitations · **Technologies:** Flask, `ibm-watsonx-ai`, Pillow · **Engineering focus:** vision prompting and web rendering; estimates are not independently validated nutrition data.

#### [AI Meeting Assistant](Build_Multimodal_Generative_AI_Applications/AI_Meeting_Assistant/README.md)

Intended meeting transcription/summarization app (Whisper + Gradio + watsonx per the lab instructions).

**Status:** Stub — lab instructions only, no implementation.

---

### Course 6 — Fundamentals of Building AI Agents

**Course status: Completed.** Four source implementations and a visualization notebook/draft explore framework-provided agents and hand-written tool-calling orchestration. See the [Course 6 overview](Fundamentals_of_Building_AI_Agents/README.md).

#### [AI Math Assistant](Fundamentals_of_Building_AI_Agents/AI_Math_Assistant/README.md)

Eight declared `@tool` functions (seven arithmetic plus Wikipedia lookup), with 37 offline tool-test functions in eight modules. `create_agent` wiring uses a fixed OpenRouter DeepSeek model, but importing `llm.py` makes a live greeting call and tool discovery selects all public callables, including imported helpers. Tool tests do not validate that startup path.

**Status:** Implemented tools with experimental agent wiring · **Technologies:** LangChain 1.x, LangGraph, `langchain-openai`, Wikipedia, pytest · **Engineering focus:** tool contracts, registry correctness, mocked external calls, import-time behavior.

#### [AI-Powered Data Analysis with LCEL](Fundamentals_of_Building_AI_Agents/AI_Powered_Data_Analysis_with_LCEL/README.md)

Conversational CSV agent with six tools: file listing, preload/cache, schema summaries, dataframe-method dispatch, RandomForest classification accuracy, and regression R²/MSE probes. It retains Breast Cancer Wisconsin and California Housing datasets and uses `create_openai_tools_agent` + `AgentExecutor` (15 iterations) on OpenRouter. Nine test functions exercise local behavior; the import/configuration check needs a nonempty key setting, which can be a dummy value for offline tests. No measured ML score is asserted here.

**Status:** Implemented data-agent extension · **Technologies:** LangChain 0.3.x, `langchain-openai` (OpenRouter), pandas, scikit-learn · **Engineering focus:** data-tool contracts, evidence-backed task classification, error-shaped tool returns.

> Note: despite the directory name, the data-analysis agent uses the tools-agent pattern, not an LCEL `prompt | llm | parser` pipe.

#### [Tool-Calling Agent](Fundamentals_of_Building_AI_Agents/Tool_calling_Agent/README.md)

Manual tool-calling loop on the IBM watsonx stack: the model is bound to five YouTube tools (`search_youtube`, `extract_video_id`, `fetch_transcript`, `get_full_metadata`, `get_thumbnails`) via `llm.bind_tools(...)`, and a hand-written executor runs the requested `tool_calls` and returns each result as a `ToolMessage` linked by `tool_call_id`. The loop in `src/run_agent.py` repeats invoke → execute → append until the model answers without tool calls, capped at `MAX_ITERATIONS = 10`.

**Status:** Implemented manual agent (no test suite) · **Technologies:** LangChain 1.x, `langchain-ibm`, `ibm-watsonx-ai`, pytube, yt-dlp, YouTube Transcript API · **Engineering focus:** binding vs. execution, linked `ToolMessage` history, error observations.

#### [NL-to-SQL Agent](Fundamentals_of_Building_AI_Agents/NL_SQL_Agent/README.md)

Natural-language questions against MySQL/Chinook: `llm_agent.py` builds a configured watsonx model, and `sql_agent.py` connects through SQLAlchemy/`SQLDatabase` and runs `create_sql_agent` via `--prompt`. The project retains the SQL dump. Earlier notes recorded `347` albums; that historical integration run was not repeated for this documentation update.

**Status:** Implemented guided SQL-agent lab · **Technologies:** LangChain SQL agent/`SQLDatabase`, `ChatWatsonx`, SQLAlchemy, MySQL (Chinook) · **Engineering focus:** connection-URL construction and model → connection → schema → agent debugging.

#### [Data Visualization Agent](Fundamentals_of_Building_AI_Agents/Data_Visualization_Agent/README.md)

Guided notebook on conversational charting with `create_pandas_dataframe_agent` over a student dataset. `main.py` sketches the watsonx/dataframe-agent pattern and prints generated chart-tool input, but has placeholder credentials and unspecified legacy dependencies.

**Status:** Notebook retained; standalone draft incomplete · **Technologies:** `langchain-experimental`, IBM SDKs, pandas/matplotlib references · **Engineering focus:** natural-language-to-chart concepts and intermediate-step inspection. No standalone manifest, effective env reader, or verified execution command is provided.

**Key things learned (Course 6)**

- Binding is not executing: `bind_tools` only exposes tool schemas; application code must run requested tools and return observations.
- Tool-call lifecycle: keep the assistant's tool-call message plus the linked `ToolMessage` results (`tool_call_id`) so the model associates requests with observations.
- Agent control flow: handle normal completion and iteration limits as distinct exits; a hard-coded limit message is not a model answer.
- Errors as observations: returning tool failures to the model (unknown tool, bad args, wrong task-type probe) lets the agent recover instead of crashing.
- Tool and prompt design shape behavior: docstrings are the model's contract; system instructions encode policy (e.g. classification probe for discrete labels only).
- Debugging and hygiene: validate model, config, schema, tools, and orchestration layer by layer; pin versions against actual API signatures; report missing env vars by name without exposing secrets.

---

### Course 7 — Agentic AI with LangChain and LangGraph

**Course status: Completed.** Five implementations cover stateful routing, Reflection, Reflexion, ReAct, and multi-agent document RAG. See the [Course 7 overview](Agentic_AI_with_LangChain_and_LangGraph/README.md).

#### [LangGraph Stateful AI Workflows](Agentic_AI_with_LangChain_and_LangGraph/LangGraph_Stateful_AI_Workflows/README.md)

Toy authentication routing and canned-context QA show `TypedDict` state, partial updates, fixed/conditional edges, and cycles. Authentication uses demo values rather than a real auth system; QA uses a configured watsonx client. The retained counter exercise is a notebook stub.

**Status:** Implemented guided workflows with validation/credential-printing caveats · **Engineering focus:** state contracts, routing, input vs. context vs. model invocation.

#### [Reflection Agent](Agentic_AI_with_LangChain_and_LangGraph/Reflection_Agent_with_LangGraph/README.md)

Two-node `MessageGraph`: generate a LinkedIn draft → critique as a human-role message → revise. The demo produces four drafts and three critiques before a message-count stop. It has no fact checker, quality ranking, or enforced character limit.

**Status:** Implemented guided pattern · **Engineering focus:** message roles, LCEL chains, explicit feedback, bounded iteration.

#### [Deep Research Reflexion Agent](Agentic_AI_with_LangChain_and_LangGraph/Deep_Research_Reflexion_Agent/README.md)

Draft/self-critique/search queries → Tavily research → revised answer with references. A three-node legacy `MessageGraph` uses tool-call schemas and a fixed research-message budget. Eight test modules contain 45 functions with model/search fakes; the example's biased nutrition persona is not a factual or clinical verifier.

**Status:** Implemented educational research loop · **Engineering focus:** schema-guided calls, evidence context, tool-result linking, revision and termination tests.

#### [ReAct Agent with LangGraph](Agentic_AI_with_LangChain_and_LangGraph/ReAct_Agent_with_LangGraph/README.md)

Two-node `StateGraph` with four registered tools: Tavily search, keyword clothing advice, bounded AST arithmetic, and a grounded news summarizer. The tool executor returns linked `ToolMessage`s and error observations. Eleven test modules contain 56 functions, some parameterized. The limit counts tool-result messages and can stop with pending calls, so termination is not always an answered task.

**Status:** Implemented educational agent with offline tests · **Engineering focus:** lazy factories, registry/tool contracts, safe arithmetic, routing and mocked end-to-end cycles.

#### [DocChat Multi-Agent RAG](Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/README.md)

Gradio document uploads → Docling conversion/cache → BM25 + Chroma/SLATE hybrid retrieval → relevance, research, and verification stages in LangGraph. Research retries are capped at three. Six test modules contain 108 functions/methods. Verification lacks the original question, retries reuse context without verifier feedback, and embedding input is truncated to three tokens in source.

**Status:** Implemented experimental RAG app · **Engineering focus:** document contracts, shared evidence, explicit unverified outcomes, conversion/configuration tests.

---

### Course 8 — Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI

**Course status: Completed.** Seven project directories compare graph workflows, task crews, conversational agents, and requirement-driven agents. See the [Course 8 overview](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/README.md).

#### [LangGraph Workflow Patterns](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Workflow-Patterns/README.md)

Three guided patterns: sequential resume-summary/cover-letter generation, intent-based summarization/translation routing, and parallel French/Spanish/Japanese translation with aggregation. Graph images and a local Graphviz rendering utility are retained. Several nodes construct watsonx clients on import; no automated suite is tracked.

#### [LangGraph Orchestration & Evaluation](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation/README.md)

- [Parallel meal planning](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation/01-parallel-meal-planning/README.md): structured dish decomposition, dynamic `Send` fan-out, `operator.add` worker results, and Python synthesis.
- [Investment reflection](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation/02-investment-advisor-reflection/README.md): target-grade selection → generate → evaluate → feedback-driven refine. The `n > 5` stop allows six evaluations and routes to `Accepted` even on an unmatched grade.

Five modules contain 44 test functions/methods covering both workflows with fakes. These are implemented pattern studies, not validated financial/recipe services.

#### [NourishBot](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/NourishBot/README.md)

Four agents/four tasks form two CrewAI food-image workflows: ingredient detection → dietary filtering → recipe suggestions, or nutrition analysis. YAML prompts, explicit task context, narrow watsonx tools, and structured output models support a Gradio UI. The tools read three watsonx settings, but agents rely on a separately configured default reasoning model.

**Status:** Implemented guided lab with local configuration limitations · **Engineering focus:** role/task boundaries, context passing, tool/model separation.

#### [Crew Research to Content](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/Crew_Research_2_Content/README.md)

Sequential researcher → blog writer → social-media drafter crew, using Serper search and a configured `crewai.LLM`. The example prints task outputs and token metadata; it does not publish posts. No dependency manifest or tests are tracked, and Serper configuration is required despite being absent from the template.

**Status:** Experimental implementation · **Engineering focus:** agent/task separation, sequential context, provider routing.

#### [MealMind — CrewAI Meal Planner](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/MealMind-CrewAI-Meal-Planner/README.md)

Five agents/tasks cover recipe search, shopping organization, budget suggestions, YAML-configured leftovers, and summary. Meal/shopping schemas and declared output files are present. The default runner supplies `servings` while its first task expects `{seervings}`, blocking that workflow; no successful generated report or test result is claimed.

**Status:** Experimental / incomplete execution · **Engineering focus:** structured task outputs, explicit context, input-name consistency.

#### [AG2 Lab](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/AG2-Lab/README.md)

Scripts explore `ConversableAgent`, local code execution, tool registration, structured output, human input, tutoring, and group chat, including the AutoMed subdirectory. Imports use the AG2/`autogen` API; Microsoft's `autogen_agentchat`/`autogen_core` packages listed in the mixed manifest are different APIs. Provider compatibility is not established by these examples alone.

**Status:** Implemented educational scripts · **Engineering focus:** conversational orchestration, tool/code execution, termination contracts.

#### [BeeAI Framework Lab](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/BeeAI-Framework-Lab/README.md)

`RequirementAgent` examples include tools, reasoning middleware, conditional/permission requirements, structured output, and handoff-based multi-agent travel planning. Most use watsonx; two use Gemini. The standalone factory demo passes a full identifier where only a short provider key is accepted, and is documented as blocked. Wiki scripts are live exercises, not an offline test suite.

**Status:** Experimental framework-pattern implementations · **Engineering focus:** requirements, human approval, tool emitters, handoffs, provider configuration.

### Course 9 — Build AI Agents using MCP

**Next — not started.** Upcoming topics from the official syllabus:

- MCP architecture, components, and use cases.
- FastMCP servers with tools, resources, and prompts.
- MCP clients connecting to one or multiple servers.
- STDIO and Streamable HTTP transports.
- Sampling, roots, permission-based approval, and secure MCP workflows.

No Course 9 implementation or completed-course directory is present.

### Course 10 — RAG and Agentic AI Capstone Project

**Not started.** The final capstone is intended to integrate data processing,
multimodal retrieval, multi-agent orchestration, and MCP into an end-to-end AI
system. No capstone implementation or course directory is present.

---

## Technical Skills Demonstrated

This section reflects retained source across Courses 1–8, with experimental and
incomplete workflows qualified in their project READMEs. Course-only concepts
and engineering lessons from extracted repositories are identified separately.

### LLM Application Development

- Python with project-specific version/dependency requirements (the packaged Course 7 agents require Python 3.12)
- **OpenRouter** chat-completions in the Flask/text/audio/data agents; **IBM watsonx.ai** across RAG, vision, LangGraph, CrewAI tools, and conversational labs; **Gemini** through BeeAI adapters in two examples
- Prompt engineering: `PromptTemplate`/`ChatPromptTemplate`, few-shot examples, system prompts, partial vs. input variables
- Structured outputs: Pydantic format schemas, `JsonOutputParser`, structured tool calls, and CrewAI output models; explicit deterministic validation in the vocabulary app
- LangChain chains and agents: **LCEL** (`prompt | llm | parser`), `create_openai_tools_agent` + `AgentExecutor`, `langchain.agents.create_agent` (LangGraph-backed)
- Flask web apps (routes, JSON APIs, template rendering) and FastAPI services
- Multi-model experimentation and side-by-side comparison (latency, length, quality scoring)
- Vanilla JS/CSS frontends with `fetch`, escaped text fields, and side-by-side result rendering; output/type validation remains important

### RAG

- Full pipeline: load → split → embed → store → retrieve → generate
- Chunking: `RecursiveCharacterTextSplitter` for YouTube transcripts; Markdown heading splitting and content-keyed document caching in DocChat
- Embeddings: local `all-MiniLM-L6-v2`; watsonx `ibm/granite-embedding-278m-multilingual` in YouTube RAG and `ibm/slate-125m-english-rtrvr-v2` in DocChat
- Retrieval: FAISS similarity search; DocChat's BM25 + Chroma ensemble with shared evidence across relevance/research/verification stages
- Hand-written chunked summarization and grounded context prompts, with explicit unsupported/unverified paths where implemented
- **Studied in Course 2:** LlamaIndex indexing/query-engine/retriever concepts; the unavailable Icebreaker entry does not provide runnable LlamaIndex source here

### Vector Databases

- **ChromaDB** — collections, CRUD/upsert, persistence (`PersistentClient`), `query()` with `where` filters
- **FAISS** — vector Q&A over YouTube transcripts (`langchain-community`)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dimensional text embeddings; distance is selected by the collection, not the model
- Metadata filtering: `$in`, `$gte`, `$lte`, `$and`, `$or`; combined semantic + metadata search

### Multimodal

- Vision-language models via OpenRouter (captioning, VQA, counting, extraction) and watsonx Llama-4 vision (style analysis, nutrition coaching)
- Image handling: base64 encoding, Pillow loading, torchvision preprocessing, ResNet50 embedding similarity
- Speech: gTTS narration in Storyteller and Vocabulary; Whisper is an instructions-only Meeting Assistant topic
- Serving: Gradio and Flask; FastAPI/Uvicorn and Docker/Compose definitions in Image Captioning have documented upload/packaging limitations

### Agents & Automation

- `@tool`-based tool calling, OpenAI-style function-calling agents, bounded agent loops with max iterations
- Manual tool-calling loops (`bind_tools` + `ToolMessage` history) and NL-to-SQL (`create_sql_agent` + `SQLDatabase`/MySQL); dataframe-agent work is retained as a guided notebook/incomplete visualization draft
- **LangGraph:** state schemas, message reducers, conditional routing, cycles, Reflection/Reflexion/ReAct, parallel fan-out, `Send` workers, evaluator-optimizer loops
- **CrewAI:** agents/tasks, sequential processes, explicit task context, YAML `CrewBase` configuration, Serper search, structured output models, Gradio integration
- **AG2:** `autogen` conversational agents, group-chat coordination, human input, registered functions, and local code execution
- **BeeAI:** `RequirementAgent`, tools, memory, trajectory middleware, conditional/permission requirements, and handoff-based multi-agent routing
- **Verification/evaluation:** DocChat's separate relevance/research/verification stages and feedback-driven investment refinement, with the inputs/termination limitations documented

### Testing & Evaluation

Counts are verified from tracked source definitions, **not executed pass results**.
Test modules exclude `conftest.py`; parameterized cases are not expanded.

| Project | Test modules | Test functions/methods | Evidence and scope |
|---|---:|---:|---|
| Books Advanced Search | 3 | 5 | Print-based exercises, no behavior assertions; local embeddings/storage affect runs |
| Image Captioning | 8 (7 unit + 1 pipeline) | 47 | Mocked provider/pipeline and JSON-case structure; import-time model/key config required |
| Vocabulary Storyteller | 5 | 77 | Input/JSON/coverage/retry/audio behavior with LLM/TTS fakes |
| Math Assistant | 8 | 37 | Tool behavior; Wikipedia mocked; live agent startup not covered |
| Data Analysis | 1 | 9 | Local dataset tools and a model-import check requiring a nonempty dummy key |
| Deep Research Reflexion | 8 | 45 | Schemas, configuration, chains, search execution, routing, mocked workflow |
| ReAct | 11 | 56 | Tools, safe calculator, message linking, lazy clients, routing, mocked cycles |
| DocChat | 6 | 108 | Document handling, configuration, agent/workflow behavior with fakes |
| LangGraph Orchestration & Evaluation | 5 | 44 | Worker/reducer behavior, evaluator routing, shared utilities, mocked execution |

**Total: 55 test modules and 428 test functions/methods.** No coverage percentage,
new pass count, or live-model benchmark is claimed. Image Captioning's five JSON
cases are qualitative expectations, not automated answer-quality scores.
Job Matcher's Hit@K/Precision@K evaluation is planned, not implemented.

### Next Learning Stage — MCP/FastMCP

Course 9 introduces MCP servers/clients, tools/resources/prompts, STDIO and
Streamable HTTP, sampling/roots, permission-based approval, and secure workflows.
MCP/FastMCP is not implemented in this repo yet; LangGraph, CrewAI, AG2, and BeeAI
already have retained Course 7/8 source.

---

## Engineering Concepts & Lessons

- **LLM apps are probabilistic + deterministic.** A parsed dict is not automatically validated. Keep schema guidance, JSON decoding, type/range checks, and workflow acceptance as separate contracts.
- **Why RAG is needed.** Models know nothing about your data unless it enters the prompt. RAG is the discipline of retrieving the right context so answers are grounded and current.
- **Embeddings capture meaning.** Similar sentences → similar vectors; chunk quality directly affects retrieval quality.
- **Retrieval quality limits generation quality.** Inspect retrieved context, embedding truncation, metadata, and collection lifecycle before assuming a better generation prompt will fix grounding.
- **Frameworks wrap a small set of ideas.** LlamaIndex's query engine is "embed → top-k → context → LLM"; LCEL is `prompt | model | parser`. Knowing the steps makes provider swaps (watsonx → OpenRouter touched only factories) and framework choices easy.
- **Feedback is only useful if the next node receives it.** The investment optimizer consumes feedback; DocChat retries currently repeat research with the same question/context and no verifier findings.
- **Termination is not success.** ReAct can stop with pending tool calls; the investment loop uses `Accepted` for both a grade match and a limit exit. Inspect final state rather than equating `END` with completion.
- **External-project lesson — deterministic gates.** The extracted Personal Branding Agent uses evidence/number/date checks with an advisory judge; those publishing gates are not current source in this IBM checkout.
- **External-project lesson — idempotency.** Content-hash intents, duplicate checks, and durable publishing state belong to the [standalone Personal Branding Agent](https://github.com/AlaaBadawii/PersonalBrandingAgent), illustrating lessons beyond the course labs.
- **Imports and interfaces are engineering boundaries.** Lazy factories can still be called at import time; a local image service is not automatically a working upload route; model IDs, UI labels, and package APIs can drift.
- **Debugging order matters.** Key → network → chain directly → Flask → UI isolates failures fast.

---

## Related Repositories

This IBM repository is one part of a broader progression toward AI engineering.
Both related URLs below were verified against their public GitHub repositories.

### [AI-Agents — AI Agents From Scratch](https://github.com/AlaaBadawii/AI-Agents)

In parallel, this separate repository implements the underlying mechanics directly:

- agent loops (call LLM → parse → execute tools → repeat)
- decorator-based tool registries and tool schemas
- tool calling (OpenAI-style `tool_calls` protocol)
- lightweight multi-agent orchestration and routing
- deterministic validation and Judge/Critic evaluation

The two repositories are **complementary, not integrated**:

- **IBM repository** → guided study, local implementations, and extensions using LangChain, LangGraph, CrewAI, AG2, BeeAI, RAG, and multimodal patterns; MCP is next.
- **[AI-Agents repository](https://github.com/AlaaBadawii/AI-Agents)** → understanding agent loops, tools, routing, and evaluation from first principles.

Together they represent:

```
Understand the abstractions
          ↓
Understand what is underneath them
          ↓
Learn when to use each approach
          ↓
Build production-oriented AI systems
```

### [PersonalBrandingAgent — Abu Prompt](https://github.com/AlaaBadawii/PersonalBrandingAgent)

The extracted Course 2 extension is maintained independently. It demonstrates
evidence-grounded content generation, retrieval/verification, duplicate-safe
publishing, and operational state. Its setup, tests, and deployment status belong
to that repository; it is not included in this checkout's project or test counts.

---

## Repository Structure

```text
IBM/
├── Develop_Generative_AI_Applications_Get_Started/    # Course 1 — COMPLETED
│   ├── README.md
│   ├── GenAI_Flask_App/                             # Flask + LangChain structured JSON output
│   ├── AI_Email_Assistant/                          # multi-model email generator + Compare All (+ plan.md)
│   └── Book_Movie_Advisor/                          # mood → structured recommendations
├── Build_RAG_Applications_Get_Started/                # Course 2 — COMPLETED
│   ├── README.md
│   ├── icebreaker                                   # UNAVAILABLE gitlink; not runnable source
│   └── Gradio/                                      # sentence builder + experimental image script
├── Vector_Databases_for_RAG_An_Introduction/          # Course 3 — COMPLETED
│   ├── README.md
│   ├── Books_Advanced_Search/                       # ChromaDB book search + tests
│   ├── Food_Recommendation_System/                   # experimental search/RAG; execution blockers
│   ├── Similarity_Search_on_Employee_Records/        # ChromaDB fundamentals demo
│   └── job_description_matcher/                      # plan + README (implementation pending)
├── Advanced_RAG_with_Vector_Databases_and_Retrievers/ # Course 4 — COMPLETED
│   ├── README.md
│   └── youtube-rag-summarizer/                       # transcript summarize + FAISS Q&A (+ PLAN.md)
├── Build_Multimodal_Generative_AI_Applications/      # Course 5 — COMPLETED
│   ├── README.md
│   ├── Image_Captioning/                             # CLI/Gradio, experimental API/container (+ tests)
│   │   └── evaluation/README.md                     # qualitative cases; no quality-scoring runner
│   ├── Vocab_Learning_App/                           # vocab → JSON lesson → MP3 (+ tests)
│   ├── Personal_Storyteller/                         # story + narration mini-app
│   ├── Style_Finder/                                 # outfit embedding match + Llama-4 analysis
│   ├── cal_coach_app/                                # Flask nutrition coach (Flask + watsonx vision)
│   └── AI_Meeting_Assistant/                         # stub: lab instructions only
├── Fundamentals_of_Building_AI_Agents/               # Course 6 — COMPLETED
│   ├── README.md
│   ├── AI_Math_Assistant/                            # tool-calling math + Wikipedia agent (+ tests)
│   ├── AI_Powered_Data_Analysis_with_LCEL/            # CSV classification/regression agent (+ tests, data)
│   ├── Tool_calling_Agent/                           # manual bind_tools loop over YouTube tools (watsonx)
│   ├── NL_SQL_Agent/                                 # NL-to-SQL agent over MySQL Chinook (+ README)
│   └── Data_Visualization_Agent/                     # pandas dataframe-agent lab (notebook + draft script)
├── Agentic_AI_with_LangChain_and_LangGraph/           # Course 7 — COMPLETED
│   ├── README.md
│   ├── LangGraph_Stateful_AI_Workflows/              # toy auth/QA graphs + notebook exercises
│   ├── Reflection_Agent_with_LangGraph/              # generate/critique message loop
│   ├── Deep_Research_Reflexion_Agent/                 # Tavily-backed refinement (+ tests)
│   ├── ReAct_Agent_with_LangGraph/                    # four-tool ReAct graph (+ tests)
│   └── DocChat_Multi_Agent_RAG/                       # Docling + hybrid retrieval + verification (+ tests)
├── Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/ # Course 8 — COMPLETED
│   ├── README.md
│   ├── LangGraph-Workflow-Patterns/                  # sequential, routing, parallel translation
│   ├── LangGraph-Orchestration-Evaluation/
│   │   ├── 01-parallel-meal-planning/README.md
│   │   └── 02-investment-advisor-reflection/README.md
│   ├── NourishBot/                                   # CrewAI food-image lab; separate model config
│   ├── Crew_Research_2_Content/                      # experimental research/blog/social crew
│   ├── MealMind-CrewAI-Meal-Planner/                  # experimental planner; default runner blocked
│   ├── AG2-Lab/                                      # autogen conversational API; AutoMed subdirectory
│   └── BeeAI-Framework-Lab/                          # requirement/tool/handoff examples
├── .env.example                                     # OPENROUTER_API_KEY placeholder (root convention)
├── .gitignore                                       # .env, venvs, __pycache__, local chroma/state snapshots
└── README.md                                        # this file
```

Course-level overviews: [1](Develop_Generative_AI_Applications_Get_Started/README.md) · [2](Build_RAG_Applications_Get_Started/README.md) · [3](Vector_Databases_for_RAG_An_Introduction/README.md) · [4](Advanced_RAG_with_Vector_Databases_and_Retrievers/README.md) · [5](Build_Multimodal_Generative_AI_Applications/README.md) · [6](Fundamentals_of_Building_AI_Agents/README.md) · [7](Agentic_AI_with_LangChain_and_LangGraph/README.md) · [8](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/README.md).

This is a project-level tree, not a listing of generated environments or caches.
The unavailable gitlink is explicitly marked; the extracted agent and Courses 9/10
do not have source directories in this checkout.

---

## Setup

Use separate project environments: manifests retain different LangChain/framework
generations. Most projects have a manifest, but several minimal labs do not;
their READMEs list actual imports and missing setup details. **Keep local `.env`
files out of Git.**

1. Choose a project and its required Python version, then create an environment in that directory (Python 3.12 for the packaged Course 7 agents):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Where a `requirements.txt` exists, install that project's dependencies:

```bash
python -m pip install -r requirements.txt
```

Image Captioning uses `python -m pip install -e .` with its `pyproject.toml`.
ReAct and Deep Research Reflexion also use editable installation for their
`src/` packages; their `requirements-dev.txt` includes runtime and test dependencies.
Refer to project notes for additional direct imports or packaging limitations.

3. Where a project template exists, copy it and supply your own effective values:

```bash
cp .env.example .env
```

The root template contains only `OPENROUTER_API_KEY`; it does not configure every
project. Some lab scripts have fixed Skills Network configuration and no env
reader. Research to Content and MealMind also require a Serper key absent from
their templates. A template copy does not repair implementation or missing-data
limitations.

### Environment variables used by the projects

Variable **names** only — placeholders, never real values.

Direct application reads are listed below unless a framework adapter is explicitly
identified. Optional variables have defaults; project READMEs describe exact startup behavior.

| Project | Consumed configuration and scope |
|---|---|
| C1 [GenAI Flask App](Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App/README.md) | `OPENROUTER_API_KEY`; optional `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME`. Base URL/model IDs are code constants |
| C1 [Email](Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant/README.md) / [Advisor](Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor/README.md) | `OPENROUTER_API_KEY`; model IDs/base URL are code constants |
| C2 [Gradio](Build_RAG_Applications_Get_Started/Gradio/README.md) | No env variables or hosted-model key read |
| C3 [Books](Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search/README.md) | No API key. Legacy `BOOKS_DATA` is read but not parsed into records; leave unset |
| C3 [Food](Vector_Databases_for_RAG_An_Introduction/Food_Recommendation_System/README.md) | No env reader; RAG script has fixed Skills Network watsonx configuration |
| C3 [Employee Records](Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records/README.md) / [Job Matcher](Vector_Databases_for_RAG_An_Introduction/job_description_matcher/README.md) | Employee search needs no API key; Job Matcher has no implementation |
| C4 [YouTube RAG](Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer/README.md) | No app env reader; fixed Skills Network URL/project/model configuration |
| C5 [Image Captioning](Build_Multimodal_Generative_AI_Applications/Image_Captioning/README.md) | Required at import: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`; optional `OPENROUTER_BASE_URL`, `OPENROUTER_FALLBACK_MODEL` |
| C5 [Vocabulary](Build_Multimodal_Generative_AI_Applications/Vocab_Learning_App/README.md) | `LLM_API_KEY`; optional `LLM_BASE_URL`, `LLM_MODEL`, `MAX_VOCABULARY_ITEMS`, `LLM_REQUEST_TIMEOUT`, and startup process variable `GRADIO_SHARE` |
| C5 [Personal Storyteller](Build_Multimodal_Generative_AI_Applications/Personal_Storyteller/README.md) | `LLM_API_KEY`; optional `LLM_BASE_URL`, `LLM_MODEL`; no project template |
| C5 [Style Finder](Build_Multimodal_Generative_AI_Applications/Style_Finder/README.md) / [Cal Coach](Build_Multimodal_Generative_AI_Applications/cal_coach_app/README.md) | No credential env reader; fixed Skills Network setup. Style Finder also lacks the required tracked catalog dataset |
| C5 [Meeting Assistant](Build_Multimodal_Generative_AI_Applications/AI_Meeting_Assistant/README.md) / C6 [Visualization](Fundamentals_of_Building_AI_Agents/Data_Visualization_Agent/README.md) | Stub/draft: no effective env reader or complete runnable configuration |
| C6 [Math](Fundamentals_of_Building_AI_Agents/AI_Math_Assistant/README.md) | `OPENROUTER_API_KEY`, `BASE_URL` (set for OpenRouter); model ID is fixed; import invokes a live greeting |
| C6 [Data Analysis](Fundamentals_of_Building_AI_Agents/AI_Powered_Data_Analysis_with_LCEL/README.md) | `OPENROUTER_API_KEY`; optional `OPENROUTER_BASE_URL` or `BASE_URL`, `OPENROUTER_MODEL` |
| C6 [Tool-Calling Agent](Fundamentals_of_Building_AI_Agents/Tool_calling_Agent/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_PROJECT_NAME`, `WATSONX_URL`, `WATSONX_MODEL_ID` |
| C6 [SQL Agent](Fundamentals_of_Building_AI_Agents/NL_SQL_Agent/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`; `MYSQL_USERNAME`, `MYSQL_PASSWORD`, `MYSQLHOST`, `MYSQL_PORT`, `DB_NAME` |
| C7 [Deep Research](Agentic_AI_with_LangChain_and_LangGraph/Deep_Research_Reflexion_Agent/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`, `TAVILY_API_KEY` |
| C7 [ReAct](Agentic_AI_with_LangChain_and_LangGraph/ReAct_Agent_with_LangGraph/README.md) | Same four watsonx variables and `TAVILY_API_KEY`; optional `REACT_MAX_ITERATIONS` |
| C7 [Stateful](Agentic_AI_with_LangChain_and_LangGraph/LangGraph_Stateful_AI_Workflows/README.md) / [Reflection](Agentic_AI_with_LangChain_and_LangGraph/Reflection_Agent_with_LangGraph/README.md) | Four watsonx variables plus `WATSONX_PROJECT_NAME` required by startup checks; auth-only workflow needs no IBM key |
| C7 [DocChat](Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID` via `pydantic-settings`; effective retrieval/cache/Docling options in project README |
| C8 [Workflow Patterns](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Workflow-Patterns/README.md) / [Orchestration](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID` |
| C8 [Research to Content](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/Crew_Research_2_Content/README.md) / [MealMind](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/MealMind-CrewAI-Meal-Planner/README.md) | Four watsonx variables passed to `crewai.LLM`, plus required `SERPER_API_KEY` (not in templates); provider routing is integration-specific |
| C8 [NourishBot](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/NourishBot/README.md) | `WATSONX_API_KEY`, optional `WATSONX_URL`, `WATSONX_PROJECT_ID` for tools; CrewAI default reasoning-model configuration is separate |
| C8 [AG2](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/AG2-Lab/README.md) | `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`; OpenAI-compatible config, not a `ChatWatsonx` client |
| C8 [BeeAI](Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/BeeAI-Framework-Lab/README.md) | Framework adapters consume `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, optional `WATSONX_URL`, or `GEMINI_API_KEY`; `text.py` alone reads `OPENROUTER_API_KEY` |

`WATSONX_PROJECT_NAME` is not an effective setting for ReAct, Deep Research,
DocChat inference, AG2, or BeeAI. BeeAI's model IDs are hardcoded, so template
`WATSONX_MODEL_ID`/`GEMINI_CHAT_MODEL` do not override them. DocChat's
`CACHE_EXPIRE_DAYS` is declared but its cache TTL remains fixed. Icebreaker and
the extracted agent do not supply local configuration rows for this checkout.

Provider accounts/model access are required for live workflows. A key does not
guarantee that a configured model is available or free.

### Running the apps

Commands below are statically matched to tracked entry points. Run from the
specified working directory after following the linked project setup; no live
execution result is claimed.

| Working directory (relative to repository root) | Representative command | Prerequisites/limits |
|---|---|---|
| `Develop_Generative_AI_Applications_Get_Started/GenAI_Flask_App` | `python app.py` or `python llm_test.py` | OpenRouter; Flask on port 5000; smoke check makes live calls |
| `Develop_Generative_AI_Applications_Get_Started/AI_Email_Assistant` | `python app.py` | OpenRouter; port 5000 |
| `Develop_Generative_AI_Applications_Get_Started/Book_Movie_Advisor` | `python app.py` | OpenRouter; port 5000 |
| `Build_RAG_Applications_Get_Started/Gradio` | `python app.py` | Sentence builder on port 7860; image experiment is not a working alternative |
| `Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search` | `python -m scripts.run_search` | Print-based exercises; `app.run_search` alone is not a runner |
| `Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records` | `python similarity_employeedata.py` | Local embedding model and compatible Chroma |
| `Advanced_RAG_with_Vector_Databases_and_Retrievers/youtube-rag-summarizer` | `python ytbot.py` | Compatible Skills Network/legacy LangChain runtime; port 7860; no manifest |
| `Build_Multimodal_Generative_AI_Applications/Image_Captioning` | `python -m src.main --image assets/image-1.jpg --task caption` | Required model/key configuration; actual image flag |
| `Build_Multimodal_Generative_AI_Applications/Image_Captioning` | `python -m src.api.gradio_app` | Temporary-file Gradio UI; API upload limitation is separate |
| `Build_Multimodal_Generative_AI_Applications/Vocab_Learning_App` | `python app.py` | LLM key plus network gTTS |
| `Build_Multimodal_Generative_AI_Applications/Personal_Storyteller` | `python main.py` | LLM key; minimal app with public sharing enabled |
| `Fundamentals_of_Building_AI_Agents/AI_Math_Assistant/src` | `python agent.py` | Flat imports, live import-time greeting, broad callable-registry caveat |
| `Fundamentals_of_Building_AI_Agents/AI_Powered_Data_Analysis_with_LCEL` | `python llm.py` | Interactive OpenRouter CSV agent |
| `Fundamentals_of_Building_AI_Agents/Tool_calling_Agent/src` | `python run_agent.py` | Interactive manual watsonx/YouTube tool loop |
| `Fundamentals_of_Building_AI_Agents/NL_SQL_Agent` | `python sql_agent.py --prompt "How many albums are there in the database?"` | watsonx plus populated MySQL/Chinook database |
| `Agentic_AI_with_LangChain_and_LangGraph/Deep_Research_Reflexion_Agent` | `python -m deep_research_agent.graph` | Editable package install, watsonx and Tavily |
| `Agentic_AI_with_LangChain_and_LangGraph/ReAct_Agent_with_LangGraph` | `python scripts/run_agent.py` | Editable package install, watsonx and Tavily |
| `Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG` | `python app.py` | watsonx and supported local documents; port 5000 |
| `Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Workflow-Patterns` | `python 01-sequential-agent-coordination/agent.py` | Configured watsonx client |
| `Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation` | `python 01-parallel-meal-planning/agent.py` | Configured watsonx client; nested workflow details in its README |
| `Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/Crew_Research_2_Content` | `python run.py` | Serper key and compatible CrewAI model/endpoint; no manifest |
| `Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/AG2-Lab` | `python mutli_agent.py` | Actual filename spelling; provider/API compatibility needs live validation |
| `Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/BeeAI-Framework-Lab` | `python minimal_agent.py` | Gemini adapter credentials and model access |

For projects with `tests/`, use `python -m pytest tests/ -v` from the **project
root** with their documented development dependencies/configuration. Do not run
Math's tests from `src/`. Data Analysis's offline import check needs a nonempty
dummy key; Image Captioning validates model/key configuration during import.

Notes:

- Model availability/pricing changes. Inspect the actual configured ID, not a stale UI label.
- Course 3 text embeddings and Style Finder's ResNet weights need first-run downloads; Course 4 uses hosted watsonx embeddings rather than local `all-MiniLM-L6-v2`.
- Food, the Gradio image experiment, Meeting Assistant, Visualization draft, MealMind, and BeeAI's standalone factory demo have explicit limitations rather than a universal fresh-clone workflow.
- Style Finder lacks the required tracked catalog dataset; Cal Coach and YouTube RAG have fixed lab authentication; NourishBot's reasoning-model configuration is separate from its tool credentials.

---

## Progress / Next Steps

**Certificate progress (November 9, 2026)**

- **Completed:** Courses 1–8, with eight course landing pages and linked project/lab documentation.
- **Next, not started:** Course 9 — Build AI Agents using MCP.
- **Not started:** Course 10 — RAG and Agentic AI Capstone Project.

**Project-level follow-up work**

- Build the plan-only Job Matcher and instructions-only Meeting Assistant; complete the Visualization draft.
- Resolve Food data/helper contracts, Image Captioning upload/packaging/result metadata, Math startup/registration, MealMind task inputs, and BeeAI factory-demo keys.
- Review DocChat embedding truncation/verification feedback and distinguish investment-limit termination from a matched grade.
- Prepare missing datasets/manifests and portable provider wiring where the lab runtime currently supplies them.
- Implement the YouTube provider-independent rebuild only as described by its separate plan.
- Icebreaker availability needs a separate repository decision; its gitlink is not a working project here. Personal Branding Agent follow-up belongs to its standalone repository.
