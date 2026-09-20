"""
A/B evaluation cho RAG pipeline — Config A (dense-only) vs Config B (hybrid + RRF).

Hai config dùng chung golden dataset, generator, evaluator, prompt và ``top_k``;
biến duy nhất thay đổi là ``use_reranking`` của ``retrieve()``.

Cách ép biến đó xuống tầng generation: ``generate_with_citation`` gọi
``retrieve(query, top_k=...)`` với ``use_reranking`` mặc định, nên script tạm
thay ``task10_generation.retrieve`` bằng một wrapper cố định cờ này. Cách đó giữ
nguyên code của Task 10 và bảo đảm hai config chỉ khác đúng một tham số.

Chạy:
    python -m group_project.evaluation.run_evaluation
    python -m group_project.evaluation.run_evaluation --limit 3   # thử nhanh
"""

import argparse
import contextlib
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

GOLDEN_PATH = HERE / "golden_dataset.json"
RAW_OUTPUT_PATH = HERE / "evaluation_raw.json"

TOP_K = 5
METRIC_NAMES = [
    "faithfulness",
    "answer_relevance",
    "context_recall",
    "context_precision",
]


# --------------------------------------------------------------------------
# Thu thập câu trả lời của hệ thống
# --------------------------------------------------------------------------


@contextlib.contextmanager
def forced_reranking(use_reranking: bool):
    """Ép ``use_reranking`` cho mọi lời gọi ``retrieve`` bên trong Task 10."""
    from src import task10_generation
    from src.task9_retrieval_pipeline import retrieve as real_retrieve

    def patched(query, top_k=TOP_K, *args, **kwargs):
        kwargs.pop("use_reranking", None)
        return real_retrieve(query, top_k=top_k, use_reranking=use_reranking)

    original = task10_generation.retrieve
    task10_generation.retrieve = patched
    try:
        yield
    finally:
        task10_generation.retrieve = original


def collect_responses(dataset: list[dict], use_reranking: bool) -> list[dict]:
    """Chạy pipeline trên toàn bộ golden dataset cho một config."""
    from src.task10_generation import generate_with_citation

    rows = []
    with forced_reranking(use_reranking):
        for index, case in enumerate(dataset, 1):
            question = case["question"]
            try:
                result = generate_with_citation(question, top_k=TOP_K)
            except Exception as error:
                print(f"  [{index}] LOI: {type(error).__name__}: {error}")
                result = {
                    "answer": f"ERROR: {type(error).__name__}",
                    "sources": [],
                    "retrieval_source": "none",
                }

            rows.append(
                {
                    "question": question,
                    "answer": result["answer"],
                    "contexts": [source["content"] for source in result["sources"]],
                    "reference": case["expected_answer"],
                    "expected_context": case["expected_context"],
                    "retrieval_source": result["retrieval_source"],
                    "source_ids": [source["id"] for source in result["sources"]],
                }
            )
            print(f"  [{index}/{len(dataset)}] {question[:60]}...")
    return rows


# --------------------------------------------------------------------------
# Chấm điểm bằng RAGAS
# --------------------------------------------------------------------------


def build_evaluator():
    """Tạo evaluator LLM + embeddings theo provider trong .env."""
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    provider = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    model = os.getenv("EVALUATOR_MODEL") or os.getenv("LLM_MODEL") or ""

    if provider == "openai":
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        llm = ChatOpenAI(model=model or "gpt-4o-mini", temperature=0)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "gemini":
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
            GoogleGenerativeAIEmbeddings,
        )

        llm = ChatGoogleGenerativeAI(model=model or "gemini-2.0-flash", temperature=0)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import OpenAIEmbeddings

        llm = ChatAnthropic(model=model or "claude-sonnet-5", temperature=0)
        # RAGAS can embeddings cho answer relevance; Anthropic khong cung cap.
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        raise ValueError(f"LLM_PROVIDER khong ho tro: {provider!r}")

    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(embeddings)


def score_with_ragas(rows: list[dict]) -> dict:
    """Trả về điểm trung bình của 4 metric cho một config."""
    from ragas import EvaluationDataset, evaluate
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    llm, embeddings = build_evaluator()

    samples = [
        {
            "user_input": row["question"],
            "retrieved_contexts": row["contexts"] or [""],
            "response": row["answer"],
            "reference": row["reference"],
        }
        for row in rows
    ]

    dataset = EvaluationDataset.from_list(samples)
    metrics = [
        Faithfulness(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=embeddings),
        LLMContextRecall(llm=llm),
        LLMContextPrecisionWithReference(llm=llm),
    ]

    result = evaluate(dataset=dataset, metrics=metrics, llm=llm, embeddings=embeddings)
    frame = result.to_pandas()

    # Tên cột của RAGAS khác tên trong rubric -> map lại cho RESULT.md.
    column_map = {
        "faithfulness": "faithfulness",
        "answer_relevancy": "answer_relevance",
        "context_recall": "context_recall",
        "llm_context_precision_with_reference": "context_precision",
    }
    scores = {}
    per_case = {}
    for column, name in column_map.items():
        if column in frame.columns:
            series = frame[column].astype(float)
            scores[name] = float(series.mean(skipna=True))
            per_case[name] = [None if value != value else float(value) for value in series]
    return {"scores": scores, "per_case": per_case, "columns": list(frame.columns)}


# --------------------------------------------------------------------------
# Báo cáo
# --------------------------------------------------------------------------


def print_comparison(scores_a: dict, scores_b: dict) -> None:
    print("\n| Metric | Config A | Config B | Delta B-A |")
    print("| --- | ---: | ---: | ---: |")
    for name in METRIC_NAMES:
        a = scores_a.get(name)
        b = scores_b.get(name)
        if a is None or b is None:
            print(f"| {name} | n/a | n/a | n/a |")
            continue
        print(f"| {name} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")

    valid = [name for name in METRIC_NAMES if name in scores_a and name in scores_b]
    if valid:
        avg_a = sum(scores_a[name] for name in valid) / len(valid)
        avg_b = sum(scores_b[name] for name in valid) / len(valid)
        print(f"| **Average** | {avg_a:.3f} | {avg_b:.3f} | {avg_b - avg_a:+.3f} |")


def worst_cases(rows: list[dict], per_case: dict, limit: int = 3) -> list[dict]:
    """Xếp hạng câu tệ nhất theo điểm trung bình 4 metric."""
    ranked = []
    for index, row in enumerate(rows):
        values = [
            per_case[name][index]
            for name in per_case
            if per_case[name][index] is not None
        ]
        if not values:
            continue
        ranked.append(
            {
                "question": row["question"],
                "mean_score": sum(values) / len(values),
                "retrieval_source": row["retrieval_source"],
                "scores": {name: per_case[name][index] for name in per_case},
            }
        )
    return sorted(ranked, key=lambda item: item["mean_score"])[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="chi chay N cau dau")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    dataset = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if args.limit:
        dataset = dataset[: args.limit]
    print(f"Golden dataset: {len(dataset)} cau, top_k={args.top_k}")

    print("\nConfig A — dense-only (use_reranking=False)")
    rows_a = collect_responses(dataset, use_reranking=False)
    print("\nConfig B — hybrid + RRF (use_reranking=True)")
    rows_b = collect_responses(dataset, use_reranking=True)

    print("\nCham diem RAGAS cho Config A...")
    result_a = score_with_ragas(rows_a)
    print("Cham diem RAGAS cho Config B...")
    result_b = score_with_ragas(rows_b)

    print_comparison(result_a["scores"], result_b["scores"])

    payload = {
        "evaluation_date": date.today().isoformat(),
        "top_k": args.top_k,
        "dataset_size": len(dataset),
        "llm_provider": os.getenv("LLM_PROVIDER"),
        "generator_model": os.getenv("LLM_MODEL"),
        "embedding_model": os.getenv("EMBEDDING_MODEL"),
        "score_threshold": os.getenv("SCORE_THRESHOLD"),
        "config_a": {
            "label": "dense-only",
            "scores": result_a["scores"],
            "rows": rows_a,
            "worst": worst_cases(rows_a, result_a["per_case"]),
        },
        "config_b": {
            "label": "hybrid + RRF",
            "scores": result_b["scores"],
            "rows": rows_b,
            "worst": worst_cases(rows_b, result_b["per_case"]),
        },
    }
    RAW_OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nKet qua chi tiet: {RAW_OUTPUT_PATH.relative_to(ROOT)}")
    print("Dung so lieu nay de dien RESULT.md (khong tu bia so).")


if __name__ == "__main__":
    main()
