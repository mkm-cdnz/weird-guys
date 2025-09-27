# Signal extraction pipeline

This folder contains utilities that implement the automated keyword/keyphrase/theme/sentiment
extraction pipeline for the `tiny_POTUS_vs_weird_guys` corpus.

## Usage

```bash
pip install -r requirements.txt
python analysis/extract_signals.py \
  --input "Corpora/tiny_POTUS_vs_weird_guys - combined_weirdos.csv" \
  --output-dir artifacts
```

The script writes the following artefacts (keyphrase extraction trims each document to the
first 1,000 characters to keep YAKE runtime manageable, and clustering considers the 500
most frequent phrases):

- `artifacts/documents.parquet`: document metadata and stable identifiers.
- `artifacts/document_keywords.parquet` / `artifacts/document_keywords.csv`: merged TF-IDF and YAKE keyword assignments per document.
- `artifacts/corpus_keyword_summary.csv`: keyword roll-up showing how often each term appears across the corpus and its average ranking.
- `artifacts/keyphrase_clusters.json`: canonical keyphrase groups derived from sentence embeddings.
- `artifacts/themes.parquet`: topic-level descriptors learned via NMF.
- `artifacts/document_themes.parquet`: top theme assignments per document with weights.
- `artifacts/document_sentiment.parquet`: VADER sentiment scores for each document.

Generated files live under `artifacts/`, which is ignored by git so the repository stays lightweight.
Re-run the script whenever the corpus changes to regenerate a fresh set of outputs.

## Finding the extracted keywords

After running the pipeline, open `artifacts/document_keywords.csv` in any spreadsheet
tool to review the per-document keywords. The CSV contains the document identifier, the
keyword, which extraction method surfaced it (`tfidf` or `yake`), and its relative rank
within that document.

For a quick corpus-level overview, inspect `artifacts/corpus_keyword_summary.csv`. It
lists how many distinct documents mention each keyword and the average rank/score it
received. You can preview the top results without leaving the terminal:

```bash
python - <<'PY'
import pandas as pd

summary = pd.read_csv("artifacts/corpus_keyword_summary.csv")
print(summary.head(10).to_string(index=False))
PY
```
