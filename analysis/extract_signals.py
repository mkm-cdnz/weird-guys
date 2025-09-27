#!/usr/bin/env python3
"""Extract keywords, keyphrases, themes, and sentiment signals from a corpus CSV.

The script operationalises the strategy outlined in earlier planning notes by:
1. Loading and normalising the corpus.
2. Deriving document-level keyword/keyphrase candidates using multiple methods.
3. Clustering keyphrases into canonical themes.
4. Running a lightweight topic model to surface document themes.
5. Scoring sentiment using VADER.
6. Persisting the resulting artefacts in Parquet/JSON for downstream analysis.

Example
-------
python analysis/extract_signals.py \
    --input "Corpora/tiny_POTUS_vs_weird_guys - combined_weirdos.csv" \
    --output-dir artifacts
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

import nltk
import yake

LOGGER = logging.getLogger(__name__)


@dataclass
class Config:
    input_path: Path
    output_dir: Path
    max_keywords: int = 15
    max_keyphrases: int = 20
    n_topics: int = 10
    random_state: int = 42
    max_chars_for_keyphrases: int = 1000
    max_phrases_for_clustering: int = 500


HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", dest="input_path", type=Path, required=True)
    parser.add_argument("--output-dir", dest="output_dir", type=Path, required=True)
    parser.add_argument("--max-keywords", dest="max_keywords", type=int, default=15)
    parser.add_argument("--max-keyphrases", dest="max_keyphrases", type=int, default=20)
    parser.add_argument("--n-topics", dest="n_topics", type=int, default=10)
    parser.add_argument("--random-state", dest="random_state", type=int, default=42)
    parser.add_argument(
        "--max-chars-for-keyphrases",
        dest="max_chars_for_keyphrases",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--max-phrases-for-clustering",
        dest="max_phrases_for_clustering",
        type=int,
        default=500,
    )
    args = parser.parse_args()
    return Config(
        input_path=args.input_path,
        output_dir=args.output_dir,
        max_keywords=args.max_keywords,
        max_keyphrases=args.max_keyphrases,
        n_topics=args.n_topics,
        random_state=args.random_state,
        max_chars_for_keyphrases=args.max_chars_for_keyphrases,
        max_phrases_for_clustering=args.max_phrases_for_clustering,
    )


def normalise_text(text: str) -> str:
    """Lowercase, strip HTML tags, and collapse whitespace."""
    if not isinstance(text, str):
        return ""
    cleaned = HTML_TAG_RE.sub(" ", text)
    cleaned = cleaned.lower()
    cleaned = WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_document_table(df: pd.DataFrame) -> pd.DataFrame:
    LOGGER.info("Building document table with stable identifiers")
    id_inputs = (
        df.get("title", "").fillna("")
        + df.get("date", "").fillna("")
        + df.get("Source", "").fillna("")
    )
    doc_ids = [stable_hash(val) if val else stable_hash(str(idx)) for idx, val in enumerate(id_inputs)]
    df = df.copy()
    df["document_id"] = doc_ids
    df["clean_text"] = df["full_text"].apply(normalise_text)
    return df


def extract_keywords(tfidf_matrix, feature_names: Sequence[str], max_keywords: int) -> List[List[tuple[str, float]]]:
    LOGGER.info("Extracting top %s TF-IDF keywords per document", max_keywords)
    keywords = []
    for row in tfidf_matrix:
        if hasattr(row, "toarray"):
            row_data = row.toarray().ravel()
        else:
            row_data = row
        top_indices = np.argsort(row_data)[-max_keywords:][::-1]
        keywords.append([(feature_names[idx], float(row_data[idx])) for idx in top_indices if row_data[idx] > 0])
    return keywords


def build_keyword_table(doc_table: pd.DataFrame, config: Config) -> tuple[pd.DataFrame, TfidfVectorizer]:
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_df=0.8,
        min_df=2,
        stop_words="english",
    )
    LOGGER.info("Fitting TF-IDF vectorizer on %s documents", len(doc_table))
    tfidf = vectorizer.fit_transform(doc_table["clean_text"].tolist())
    feature_names = np.array(vectorizer.get_feature_names_out())
    keyword_lists = extract_keywords(tfidf, feature_names, config.max_keywords)
    records = []
    for doc_id, keywords in zip(doc_table["document_id"], keyword_lists):
        for rank, (term, score) in enumerate(keywords, start=1):
            records.append(
                {
                    "document_id": doc_id,
                    "keyword": term,
                    "method": "tfidf",
                    "score": score,
                    "rank": rank,
                }
            )
    keyword_table = pd.DataFrame.from_records(records)
    return keyword_table, vectorizer


def extract_yake_keyphrases(texts: Iterable[str], config: Config) -> pd.DataFrame:
    LOGGER.info("Running YAKE keyphrase extraction")
    extractor = yake.KeywordExtractor(lan="en", n=3, top=config.max_keyphrases)
    records = []
    for doc_id, text in texts:
        truncated = text[: config.max_chars_for_keyphrases]
        source_text = truncated if truncated != text else text
        phrases = extractor.extract_keywords(source_text)
        for rank, (phrase, score) in enumerate(phrases, start=1):
            records.append(
                {
                    "document_id": doc_id,
                    "keyword": phrase,
                    "method": "yake",
                    "score": float(score),
                    "rank": rank,
                }
            )
    return pd.DataFrame.from_records(records)


def combine_keyword_tables(*tables: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat(tables, ignore_index=True)
    combined.sort_values(["document_id", "method", "rank"], inplace=True)
    return combined


def summarise_keywords(keyword_table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate keyword usage to create a human-friendly overview."""
    LOGGER.info("Summarising keyword usage across the corpus")
    if keyword_table.empty:
        return pd.DataFrame(
            columns=[
                "keyword",
                "method",
                "document_frequency",
                "total_mentions",
                "mean_rank",
                "mean_score",
            ]
        )

    summary = (
        keyword_table.groupby(["keyword", "method"], as_index=False)
        .agg(
            document_frequency=("document_id", "nunique"),
            total_mentions=("document_id", "count"),
            mean_rank=("rank", "mean"),
            mean_score=("score", "mean"),
        )
        .sort_values(
            ["document_frequency", "total_mentions", "mean_rank"],
            ascending=[False, False, True],
        )
    )
    return summary


def cluster_keyphrases(keyword_table: pd.DataFrame, config: Config) -> dict:
    LOGGER.info("Clustering keyphrases using sentence embeddings")
    phrase_series = keyword_table["keyword"].str.lower().str.strip().dropna()
    if phrase_series.empty:
        return {}

    top_phrases = (
        phrase_series.value_counts().head(config.max_phrases_for_clustering).index.tolist()
    )
    unique_phrases = np.array(top_phrases)
    if len(unique_phrases) == 0:
        return {}

    tfidf = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    phrase_matrix = tfidf.fit_transform(unique_phrases)

    if phrase_matrix.shape[1] > 1:
        n_components = min(50, phrase_matrix.shape[1] - 1)
        svd = TruncatedSVD(n_components=n_components, random_state=config.random_state)
        embeddings = svd.fit_transform(phrase_matrix)
    else:
        embeddings = phrase_matrix.toarray()

    embeddings = normalize(embeddings)

    if len(unique_phrases) == 1:
        return {0: {"canonical_phrase": unique_phrases[0], "members": [unique_phrases[0]]}}

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.4,
        metric="cosine",
        linkage="average",
    )
    labels = clustering.fit_predict(embeddings)

    clusters: dict[int, dict] = {}
    for phrase, label in zip(unique_phrases, labels):
        cluster = clusters.setdefault(
            int(label), {"canonical_phrase": phrase, "members": [], "size": 0}
        )
        cluster["members"].append(phrase)
        cluster["size"] += 1

    # Set canonical phrase as the shortest phrase in each cluster to aid readability.
    for cluster in clusters.values():
        cluster["canonical_phrase"] = min(cluster["members"], key=len)
    return clusters


def store_keyphrase_clusters(clusters: dict, path: Path) -> None:
    path.write_text(json.dumps(clusters, indent=2, ensure_ascii=False))


def fit_topic_model(doc_table: pd.DataFrame, config: Config, tfidf_vectorizer: TfidfVectorizer) -> tuple[NMF, np.ndarray]:
    LOGGER.info("Fitting NMF topic model with %s topics", config.n_topics)
    tfidf = tfidf_vectorizer.transform(doc_table["clean_text"].tolist())
    model = NMF(n_components=config.n_topics, random_state=config.random_state, init="nndsvd")
    doc_topic = model.fit_transform(tfidf)
    return model, doc_topic


def build_theme_tables(
    doc_table: pd.DataFrame,
    config: Config,
    tfidf_vectorizer: TfidfVectorizer,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model, doc_topic = fit_topic_model(doc_table, config, tfidf_vectorizer)
    feature_names = np.array(tfidf_vectorizer.get_feature_names_out())

    theme_records = []
    for idx, topic_vec in enumerate(model.components_):
        top_indices = topic_vec.argsort()[::-1][:10]
        keywords = feature_names[top_indices]
        theme_records.append(
            {
                "theme_id": f"theme_{idx:02d}",
                "top_keywords": ", ".join(keywords),
                "topic_weight_sum": float(topic_vec.sum()),
            }
        )
    theme_table = pd.DataFrame(theme_records)

    doc_theme_records = []
    for doc_id, weights in zip(doc_table["document_id"], doc_topic):
        total = weights.sum()
        if total == 0:
            continue
        sorted_indices = np.argsort(weights)[::-1]
        for rank, idx in enumerate(sorted_indices[:3], start=1):
            doc_theme_records.append(
                {
                    "document_id": doc_id,
                    "theme_id": f"theme_{idx:02d}",
                    "weight": float(weights[idx]),
                    "weight_norm": float(weights[idx] / total) if total else 0.0,
                    "rank": rank,
                }
            )
    doc_theme_table = pd.DataFrame(doc_theme_records)
    return theme_table, doc_theme_table


def score_sentiment(doc_table: pd.DataFrame) -> pd.DataFrame:
    LOGGER.info("Scoring sentiment with VADER")
    nltk.download("vader_lexicon", quiet=True)
    sia = SentimentIntensityAnalyzer()
    records = []
    for doc_id, text in zip(doc_table["document_id"], doc_table["clean_text"]):
        scores = sia.polarity_scores(text)
        compound = scores["compound"]
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        records.append(
            {
                "document_id": doc_id,
                "sentiment_label": label,
                "compound": compound,
                "positive": scores["pos"],
                "neutral": scores["neu"],
                "negative": scores["neg"],
            }
        )
    return pd.DataFrame(records)


def persist_dataframe(df: pd.DataFrame, path: Path) -> None:
    LOGGER.info("Writing %s rows to %s", len(df), path)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = parse_args()

    ensure_output_dir(config.output_dir)

    LOGGER.info("Loading corpus from %s", config.input_path)
    raw_df = pd.read_csv(config.input_path)
    doc_table = build_document_table(raw_df)

    keyword_table_tfidf, tfidf_vectorizer = build_keyword_table(doc_table, config)
    keyword_table_yake = extract_yake_keyphrases(
        doc_table[["document_id", "clean_text"]].itertuples(index=False), config
    )
    keyword_table = combine_keyword_tables(keyword_table_tfidf, keyword_table_yake)

    keyword_summary = summarise_keywords(keyword_table)
    if not keyword_summary.empty:
        preview = keyword_summary.head(10).to_string(index=False, float_format="{:.3f}".format)
        LOGGER.info("Top corpus keywords by document coverage:\n%s", preview)

    clusters = cluster_keyphrases(keyword_table, config)
    store_keyphrase_clusters(
        clusters, config.output_dir / "keyphrase_clusters.json"
    )

    # Persist document table without the clean text (to avoid duplication) and as metadata
    document_export = doc_table.drop(columns=["clean_text"])
    persist_dataframe(document_export, config.output_dir / "documents.parquet")
    persist_dataframe(keyword_table, config.output_dir / "document_keywords.parquet")
    persist_dataframe(keyword_table, config.output_dir / "document_keywords.csv")
    persist_dataframe(keyword_summary, config.output_dir / "corpus_keyword_summary.csv")

    theme_table, doc_theme_table = build_theme_tables(doc_table, config, tfidf_vectorizer)
    persist_dataframe(theme_table, config.output_dir / "themes.parquet")
    persist_dataframe(doc_theme_table, config.output_dir / "document_themes.parquet")

    sentiment_table = score_sentiment(doc_table)
    persist_dataframe(sentiment_table, config.output_dir / "document_sentiment.parquet")

    LOGGER.info("Pipeline completed successfully. Artefacts written to %s", config.output_dir)


if __name__ == "__main__":
    main()
