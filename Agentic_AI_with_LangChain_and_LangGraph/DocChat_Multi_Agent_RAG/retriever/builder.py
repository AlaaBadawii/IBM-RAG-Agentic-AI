import logging

from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain.retrievers import EnsembleRetriever
from langchain_ibm import WatsonxEmbeddings
from pydantic import SecretStr

from config.settings import settings

logger = logging.getLogger(__name__)


class RetrieverBuilder:
    """Build a hybrid retriever using BM25 and vector search."""

    def __init__(self):
        """Build hybrid retriever using BM25 and vector search."""
        if not settings.WATSONX_URL:
            raise ValueError("WATSONX_URL must be configured.")

        if not settings.WATSONX_API_KEY:
            raise ValueError("WATSONX_API_KEY must be configured.")

        if not settings.WATSONX_PROJECT_ID:
            raise ValueError("WATSONX_PROJECT_ID must be configured.")

        embed_params = {
            EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS: 3,
            EmbedTextParamsMetaNames.RETURN_OPTIONS: {"input_text": True},
        }

        self.embeddings = WatsonxEmbeddings(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            url=SecretStr(settings.WATSONX_URL),
            apikey=SecretStr(settings.WATSONX_API_KEY),
            project_id=settings.WATSONX_PROJECT_ID,
            params=embed_params,
        )

    def build_hybrid_retriever(self, docs):
        """Build a hybrid retriever using BM25 and vector search."""
        if not docs:
            raise ValueError("No documents provided to build retriever.")

        weights = settings.HYBRID_RETRIEVER_WEIGHTS
        if not weights or len(weights) != 2 or any(w < 0 for w in weights):
            raise ValueError(
                "HYBRID_RETRIEVER_WEIGHTS must be a list of two non-negative numbers."
            )

        if sum(weights) == 0:
            raise ValueError(
                "HYBRID_RETRIEVER_WEIGHTS must not be all zeros; at least one weight must be positive."
            )
        try:
            vector_store = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                persist_directory=settings.CHROMA_DB_PATH,
                collection_name=settings.CHROMA_COLLECTION_NAME
            )
            logger.info("Vector store created with %d documents.", len(docs))

            bm25_retriever = BM25Retriever.from_documents(docs)
            logger.info("BM25 retriever created with %d documents.", len(docs))

            vector_retriever = vector_store.as_retriever(
                search_kwargs={"k": settings.VECTOR_SEARCH_K}
            )
            logger.info("Vector retriever created with k=%d.", settings.VECTOR_SEARCH_K)

            hybrid_retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=weights,
            )
            logger.info(
                "Hybrid retriever created with weights: BM25=%f, Vector=%f",
                weights[0],
                weights[1], 
            )

            return hybrid_retriever

        except Exception as e:
            logger.error("Error building hybrid retriever: %s", str(e))
            raise

        
