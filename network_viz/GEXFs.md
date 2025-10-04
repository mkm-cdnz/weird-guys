

***

## Feeding GPT-5 my Colab dataframes
- [Topic ↔ top terms (bipartite):](/network_viz/topic_terms_bipartite.gexf) cleansed, stop words (mostly) removed, lemmatized, and utilized BERTopic
    - [Topics Table:](/network_viz/topics.csv) BERTopic automatically discovered 25 topics

### What I ran (summary)

- Purged every &nbsp;, Unicode NBSP (\u00A0), and any token equal to "nbsp".
- TF-IDF on 1–2 grams (min_df=8, max_df=0.9, max_features=25k).
- NMF with K=25 topics.
- Labels = top 3 terms per topic (also included top 12 per topic).
- topic_graph.gexf: nodes are topics (T0…T24), edges weighted by cosine similarity between topic-term vectors (threshold = 0.18).
- topic_terms_bipartite.gexf: two-mode graph connecting each topic to its 12 top terms (edge weight = topic-term weight).

***
