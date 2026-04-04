"""Tests for RAG Vector Integration module (RECOMMENDATIONS 6.2.8)."""

import threading
import unittest

from src.rag_vector_integration import (
    RAGVectorIntegration,
    ChunkStrategy,
    RetrievalMode,
    _tokenize,
    _term_frequency,
    _cosine_similarity,
    _estimate_tokens,
    _split_fixed,
    _split_sentences,
    _split_paragraphs,
)

SAMPLE_DOC = (
    "Machine Learning is a branch of Artificial Intelligence. "
    "Deep Learning uses neural networks with many layers. "
    "Natural Language Processing enables computers to understand text. "
    "Reinforcement Learning trains agents through rewards."
)

SAMPLE_DOC_2 = (
    "Python is a popular programming language. "
    "Python supports multiple paradigms including object oriented programming. "
    "Django and Flask are popular Python web frameworks."
)


class TestTokenize(unittest.TestCase):
    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_stopword_removal(self):
        tokens = _tokenize("this is a test of the system")
        self.assertNotIn("this", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("the", tokens)
        self.assertIn("test", tokens)
        self.assertIn("system", tokens)

    def test_short_token_removal(self):
        tokens = _tokenize("I am a b c testing")
        self.assertNotIn("b", tokens)
        self.assertNotIn("c", tokens)
        self.assertIn("testing", tokens)

    def test_empty_string(self):
        self.assertEqual(_tokenize(""), [])


class TestTermFrequency(unittest.TestCase):
    def test_normalized(self):
        tf = _term_frequency(["hello", "hello", "world"])
        self.assertAlmostEqual(tf["hello"], 2 / 3)
        self.assertAlmostEqual(tf["world"], 1 / 3)

    def test_empty(self):
        tf = _term_frequency([])
        self.assertEqual(tf, {})


class TestCosineSimilarity(unittest.TestCase):
    def test_identical_vectors(self):
        v = {"a": 1.0, "b": 2.0}
        self.assertAlmostEqual(_cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal_vectors(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        self.assertAlmostEqual(_cosine_similarity(v1, v2), 0.0)

    def test_empty_vectors(self):
        self.assertEqual(_cosine_similarity({}, {"a": 1.0}), 0.0)
        self.assertEqual(_cosine_similarity({"a": 1.0}, {}), 0.0)
        self.assertEqual(_cosine_similarity({}, {}), 0.0)

    def test_partial_overlap(self):
        v1 = {"a": 1.0, "b": 1.0}
        v2 = {"a": 1.0, "c": 1.0}
        score = _cosine_similarity(v1, v2)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class TestSplitters(unittest.TestCase):
    def test_fixed_split(self):
        text = " ".join(f"word{i}" for i in range(20))
        chunks = _split_fixed(text, 5, 1)
        self.assertGreater(len(chunks), 1)
        self.assertIn("word0", chunks[0])

    def test_sentence_split(self):
        chunks = _split_sentences("First sentence. Second sentence! Third?")
        self.assertEqual(len(chunks), 3)

    def test_paragraph_split(self):
        chunks = _split_paragraphs("Para one.\n\nPara two.\n\nPara three.")
        self.assertEqual(len(chunks), 3)

    def test_estimate_tokens(self):
        est = _estimate_tokens("hello world test")
        self.assertGreater(est, 0)


class TestDocumentIngestion(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration(chunk_size=10, chunk_overlap=2)

    def test_ingest_returns_ok(self):
        result = self.rag.ingest_document(SAMPLE_DOC, title="ML Doc")
        self.assertEqual(result["status"], "ok")
        self.assertIn("doc_id", result)
        self.assertGreater(result["chunk_count"], 0)

    def test_ingest_empty_document(self):
        result = self.rag.ingest_document("")
        self.assertEqual(result["status"], "error")

    def test_ingest_whitespace_only(self):
        result = self.rag.ingest_document("   ")
        self.assertEqual(result["status"], "error")

    def test_get_document(self):
        r = self.rag.ingest_document(SAMPLE_DOC, title="Test")
        doc = self.rag.get_document(r["doc_id"])
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["title"], "Test")

    def test_get_missing_document(self):
        self.assertEqual(self.rag.get_document("nope")["status"], "error")

    def test_remove_document(self):
        r = self.rag.ingest_document(SAMPLE_DOC)
        self.assertEqual(self.rag.remove_document(r["doc_id"])["status"], "ok")
        self.assertEqual(self.rag.get_document(r["doc_id"])["status"], "error")

    def test_remove_missing_document(self):
        self.assertEqual(self.rag.remove_document("nope")["status"], "error")

    def test_list_documents(self):
        self.rag.ingest_document(SAMPLE_DOC, title="A")
        self.rag.ingest_document(SAMPLE_DOC_2, title="B")
        listing = self.rag.list_documents()
        self.assertEqual(listing["count"], 2)

    def test_sentence_strategy(self):
        r = self.rag.ingest_document(SAMPLE_DOC, strategy=ChunkStrategy.SENTENCE)
        self.assertEqual(r["status"], "ok")
        self.assertGreaterEqual(r["chunk_count"], 2)

    def test_paragraph_strategy(self):
        text = "Paragraph one content.\n\nParagraph two content."
        r = self.rag.ingest_document(text, strategy=ChunkStrategy.PARAGRAPH)
        self.assertEqual(r["chunk_count"], 2)


class TestSemanticSearch(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration(chunk_size=10, chunk_overlap=2)
        self.rag.ingest_document(SAMPLE_DOC, title="ML")
        self.rag.ingest_document(SAMPLE_DOC_2, title="Python")

    def test_search_returns_results(self):
        result = self.rag.search("machine learning neural networks")
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["result_count"], 0)

    def test_search_empty_query(self):
        result = self.rag.search("")
        self.assertEqual(result["status"], "error")

    def test_search_top_k(self):
        result = self.rag.search("learning", top_k=2)
        self.assertLessEqual(len(result["results"]), 2)

    def test_search_scores_sorted(self):
        result = self.rag.search("learning")
        scores = [r["score"] for r in result["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_min_score_filter(self):
        result = self.rag.search("learning", min_score=0.99)
        for r in result["results"]:
            self.assertGreaterEqual(r["score"], 0.99)

    def test_search_doc_filter(self):
        r1 = self.rag.list_documents()
        first_doc_id = r1["documents"][0]["doc_id"]
        result = self.rag.search("learning", doc_filter=[first_doc_id])
        for r in result["results"]:
            self.assertEqual(r["doc_id"], first_doc_id)

    def test_search_no_matching_tokens(self):
        result = self.rag.search("xyzzy qqq zzz", min_score=0.01)
        self.assertEqual(result["result_count"], 0)


class TestContextAssembly(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration(chunk_size=10, chunk_overlap=2)
        self.rag.ingest_document(SAMPLE_DOC, title="ML")

    def test_assemble_returns_context(self):
        result = self.rag.assemble_context("machine learning")
        self.assertEqual(result["status"], "ok")
        self.assertIn("context", result)
        self.assertGreater(len(result["context"]), 0)

    def test_token_budget_respected(self):
        result = self.rag.assemble_context("learning", token_budget=10)
        self.assertLessEqual(result["token_estimate"], 10)

    def test_includes_chunk_details(self):
        result = self.rag.assemble_context("learning")
        self.assertIn("chunks_detail", result)

    def test_include_metadata_flag(self):
        result = self.rag.assemble_context("learning", include_metadata=True)
        self.assertEqual(result["status"], "ok")


class TestKnowledgeGraph(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration(chunk_size=50, chunk_overlap=5)
        self.rag.ingest_document(SAMPLE_DOC, title="ML")

    def test_build_graph(self):
        result = self.rag.build_knowledge_graph()
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["entity_count"], 0)

    def test_build_graph_single_doc(self):
        r = self.rag.ingest_document(SAMPLE_DOC_2, title="Py")
        result = self.rag.build_knowledge_graph(doc_id=r["doc_id"])
        self.assertEqual(result["status"], "ok")

    def test_build_graph_no_docs(self):
        rag2 = RAGVectorIntegration()
        self.assertEqual(rag2.build_knowledge_graph()["status"], "error")

    def test_query_graph(self):
        self.rag.build_knowledge_graph()
        result = self.rag.query_graph("Machine Learning")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["entity"]["name"], "Machine Learning")

    def test_query_graph_missing_entity(self):
        self.rag.build_knowledge_graph()
        result = self.rag.query_graph("Nonexistent Entity")
        self.assertEqual(result["status"], "error")

    def test_graph_stats(self):
        self.rag.build_knowledge_graph()
        stats = self.rag.get_graph_stats()
        self.assertEqual(stats["status"], "ok")
        self.assertIn("entity_count", stats)


class TestRAGPipeline(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration(chunk_size=10, chunk_overlap=2)
        self.rag.ingest_document(SAMPLE_DOC, title="ML")
        self.rag.ingest_document(SAMPLE_DOC_2, title="Python")

    def test_vector_mode(self):
        result = self.rag.rag_pipeline("machine learning", mode=RetrievalMode.VECTOR)
        self.assertEqual(result["status"], "ok")
        self.assertIn("prompt", result)
        self.assertIn("Question:", result["prompt"])

    def test_graph_mode(self):
        self.rag.build_knowledge_graph()
        result = self.rag.rag_pipeline("learning", mode=RetrievalMode.GRAPH)
        self.assertEqual(result["status"], "ok")

    def test_hybrid_mode(self):
        self.rag.build_knowledge_graph()
        result = self.rag.rag_pipeline("learning", mode=RetrievalMode.HYBRID)
        self.assertEqual(result["status"], "ok")

    def test_empty_query(self):
        result = self.rag.rag_pipeline("")
        self.assertEqual(result["status"], "error")

    def test_includes_sources(self):
        result = self.rag.rag_pipeline("learning", include_sources=True)
        self.assertIn("sources", result)

    def test_no_sources(self):
        result = self.rag.rag_pipeline("learning", include_sources=False)
        self.assertEqual(result["sources"], [])

    def test_system_prompt_in_output(self):
        result = self.rag.rag_pipeline("test", system_prompt="Custom prompt.")
        self.assertIn("Custom prompt.", result["prompt"])


class TestUtility(unittest.TestCase):
    def setUp(self):
        self.rag = RAGVectorIntegration()

    def test_stats_empty(self):
        s = self.rag.stats()
        self.assertEqual(s["document_count"], 0)
        self.assertEqual(s["chunk_count"], 0)

    def test_stats_after_ingest(self):
        self.rag.ingest_document(SAMPLE_DOC)
        s = self.rag.stats()
        self.assertGreater(s["document_count"], 0)
        self.assertGreater(s["vocabulary_size"], 0)

    def test_clear(self):
        self.rag.ingest_document(SAMPLE_DOC)
        self.rag.clear()
        s = self.rag.stats()
        self.assertEqual(s["document_count"], 0)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_ingest(self):
        rag = RAGVectorIntegration(chunk_size=5, chunk_overlap=1)
        errors = []

        def ingest(idx):
            try:
                r = rag.ingest_document(f"Document number {idx} has content.", title=f"D{idx}")
                if r["status"] != "ok":
                    errors.append(f"ingest {idx} failed")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=ingest, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(rag.stats()["document_count"], 10)

    def test_concurrent_search(self):
        rag = RAGVectorIntegration(chunk_size=10, chunk_overlap=2)
        rag.ingest_document(SAMPLE_DOC)
        errors = []

        def search(q):
            try:
                r = rag.search(q)
                if r["status"] != "ok":
                    errors.append(f"search failed for {q}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=search, args=(f"term{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
