### notes
- I want to increase auditability & decrease manual tasks
- I want a pipeline from my SSOT ➡️ transformation & analysis
- I already have record creation & web scraping processes established, want to find a balance between avoiding rework & avoiding technical debt

### initial steps
- changed fields
    - "**doc_id**": Primary Key (PK)
    - "**presidential_actions**" renamed ➡️ "**type**"
    - "**date**": now uses ISO-8601
- selected SSOT
    - Google Sheets "export to CSV"
    - [https://docs.google.com/spreadsheets/d/e/2PACX-1vReJx3yAd6CR-ktxijwQjUUsiFwivr7R_bX_ts2hs46X0OUJJBaKaPUAXLXVFBfoWgFIYcFL9DMq_11/pub?gid=788015928&single=true&output=csv](https://docs.google.com/spreadsheets/d/e/2PACX-1vReJx3yAd6CR-ktxijwQjUUsiFwivr7R_bX_ts2hs46X0OUJJBaKaPUAXLXVFBfoWgFIYcFL9DMq_11/pub?gid=788015928&single=true&output=csv)
 
  ...
