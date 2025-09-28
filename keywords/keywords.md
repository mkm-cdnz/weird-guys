I am iteratively experimenting with improving my ability to search & categorize my dataset.

## POC: Keywords as headers within the dataset
- Used an array formula in Google Sheets; used nested IF statements and a REGEXMATCH function.
- I would enter keywords into the spreadsheet header, and the array formula would mark Boolean TRUE/FALSE for each record
- Good enough for prototyping & manual scanning of records, but highly inefficient and not scalable.

## Keywords & themes in a JSON object

**[V1 - keywords/exploratory_keywords.JSON](keywords/exploratory_keywords.JSON)** 
- moved keywords out of the corpous dataset, and into a separate file
- added themes, in addition to keywords; attempting to capture higher-level views of the dataset
- increased both efficiency & ability to add/remove keywords
- more scalable than POC keyword exploration.

**[V2 - keywords/exploratory_keywords_v2_plus.json](keywords/exploratory_keywords_v2_plus.json)**
- expanded keywords & themes
- moved countries from ```international_relations``` theme ▶️ a separate ```geo_entities``` list.
- gender is now stored as an ```attribute``` not a theme.
- restructured JSON format 
- implemented normalization (lowercasing, normalize hyphens, strip accents)
- Introduced a built-in framing lexicon (restriction vs support, with negation) to hopefully allow me to quantify Hypothesis 1.
