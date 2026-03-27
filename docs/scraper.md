# Comprehensive Strategy for the Development of an Independent Financial Data Harvesting Engine for Indian Equities

The architectural requirement for constructing a high-fidelity financial data scraper for the Indian market, capable of matching the depth of institutional-grade platforms like Screener.in, necessitates a departure from traditional browser-based automation toward a direct interaction with the regulatory data pipelines of the National Stock Exchange (NSE) and the Bombay Stock Exchange (BSE). To avoid the legal and technical vulnerabilities associated with scraping third-party aggregators, the proposed strategy leverages the standardized Extensible Business Reporting Language (XBRL) frameworks mandated by the Ministry of Corporate Affairs (MCA) and the Securities and Exchange Board of India (SEBI). By systematically identifying hidden JSON endpoints, managing session states to circumvent anti-bot protocols, and implementing automated XBRL parsing logic, it is possible to reconstruct longitudinal five-year tables for Profit and Loss (P&L) statements, Balance Sheets, and Cash Flow statements with high precision.

## The Regulatory Foundation of Digital Financial Disclosures

The shift from unstructured PDF reports to machine-readable financial disclosures in India was accelerated by the MCA’s 2011 mandate, which required listed companies and large public firms to file their financial statements in XBRL format. This transition created a robust, structured data environment that allows for the automated extraction of granular financial facts. Understanding this foundation is critical for developing a generic scraper, as it dictates the data structures the script will encounter.

### The Extensible Business Reporting Language (XBRL) Framework

XBRL serves as the "barcode" for financial statements, where every line item is assigned a unique tag from a standardized taxonomy. For the Indian market, the MCA taxonomy is developed based on the disclosure requirements of the Companies Act, the Indian Accounting Standards (Ind AS), and Schedule III requirements. The taxonomy provides the dictionary, while the "instance document" (the actual.xml or.xbrl file) contains the specific values, units, and periods for a given company.


|                       |                                                                                     |                                                                       |
| --------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Concept**           | **Description in Indian Context**                                                   | **Role in Scraping Logic**                                            |
| **Taxonomy**          | The set of definitions for accounting terms (e.g., P&L, Balance Sheet).             | Acts as the lookup table to map raw tags to human-readable names.     |
| **Instance Document** | The specific XML file containing a company's financial data for a period.           | The primary target for the scraper to download and parse.             |
| **Context**           | Metadata defining the entity, period (instant or duration), and segment.            | Used to distinguish between "Consolidated" and "Standalone" figures.  |
| **Unit**              | Definitions for currency (INR) and scale (e.g., Crores, Millions).                  | Crucial for normalizing data points across different reporting years. |
| **Linkbases**         | XML files defining relationships like calculation rules and presentation hierarchy. | Used to reconstruct the visual structure of a financial statement.    |


The utility of XBRL over traditional HTML scraping cannot be overstated. While a website layout might change, the underlying XBRL tags for core concepts like "Revenue from Operations" or "Total Assets" remain consistent across companies and reporting periods. This consistency allows the scraper to be generic, meaning it can process any company listed on the NSE or BSE once the initial mapping is established.

### Mandatory Filing Thresholds and Compliance

Developing a robust scraper requires an understanding of which companies are required to file in machine-readable formats. Under the Companies (Filing of documents and forms in XBRL) Rules, the following classes of companies must file their Balance Sheets and P&L statements in XBRL format :

- All companies listed on any stock exchange in India and their Indian subsidiaries.
- Companies with a paid-up capital of five crore rupees (INR 50 million) or more.
- Companies with a turnover of one hundred crore rupees (INR 1 billion) or more.
- Companies required to prepare financial statements as per the Companies (Indian Accounting Standards) Rules, 2015.

The exclusion of banking, insurance, and non-banking financial companies (NBFCs) from the standard MCA XBRL filing requirement (they often use industry-specific taxonomies) means a generic scraper must include conditional logic to handle these sectors differently if they are included in the stock universe.

## Architectural Strategy for NSE Data Extraction

The National Stock Exchange of India (NSE) provides an extensive interface for corporate filings, but its public-facing website is heavily protected by session-based security and anti-scraping layers. A successful Python script must replicate the "human-in-the-loop" browsing pattern to establish a valid connection with the internal APIs.

### Technical Discovery of NSE JSON Endpoints

The NSE does not publish an official API for free programmatic use, but its front-end results pages are powered by back-end JSON endpoints that can be inspected via browser developer tools. For longitudinal financial data, the most critical endpoint is the Results Comparison API.

The specific endpoint structure identified for fetching comparative financial results is:

`https://www.nseindia.com/api/results-comparision?symbol={purified_symbol}`

The "purification" of the symbol is a prerequisite step. Many Indian stock symbols contain special characters, notably the ampersand (&). The `nsepython` library implementation reveals that such characters must be URL-encoded (e.g., converting `&` to `%26`) to prevent the server from misinterpreting the query string.

### Implementing the NSE Session Handshake

The NSE server validates requests not just by the endpoint URL, but by the presence of specific cookies and the sequence of navigation. A raw request to the API will frequently return a `403 Forbidden` or `401 Unauthorized` error. The strategy must incorporate a session-warming phase.

A robust Python implementation utilizes the `requests.Session()` object to manage state. The handshake sequence involves:

1. **Initial Visit**: Making a GET request to the NSE homepage (`https://www.nseindia.com/`) to receive the initial set of tracking cookies.
2. **Contextual Header Management**: Attaching headers that mimic a modern web browser.
3. **Intermediate Requests**: Accessing a secondary page, such as the option chain or market status, which ensures the session is fully registered in the NSE's back-end before the API call is made.


|                     |                                                          |                                                             |
| ------------------- | -------------------------------------------------------- | ----------------------------------------------------------- |
| **Header Key**      | **Required Value Example**                               | **Rationale**                                               |
| **User-Agent**      | `Mozilla/5.0 (Windows NT 10.0; Win64; x64)...`           | Prevents identification as a script.                        |
| **Accept-Language** | `en-US,en;q=0.9`                                         | Mimics browser localized settings.                          |
| **Referer**         | `https://www.nseindia.com/get-quotes/equity?symbol=SBIN` | Validates that the request originated from the official UI. |
| **Accept-Encoding** | `gzip, deflate, br`                                      | Signals ability to handle compressed data.                  |


Furthermore, for environments where simple session-tracking is insufficient (such as cloud servers frequently blocked by IP), an alternative "Curl Mode" can be implemented. This involves using system-level `curl` commands to manage a local `cookies.txt` file, which is refreshed whenever a `ValueError` indicates the response is no longer valid JSON.

### Transition to the Integrated Filing System

An emerging technical detail for NSE-focused scrapers is the "Integrated Filing - Financials" system. For financial results submitted for the quarter ended March 2025 and thereafter, the exchange is migrating filings to this consolidated dashboard. A future-proof strategy must include logic to check this specific integrated filing path if the standard results-comparison endpoint returns null for recent periods. This system is designed to provide more comprehensive, machine-ready data directly within the NSE infrastructure.

## Architectural Strategy for BSE Data Extraction

The Bombay Stock Exchange (BSE) maintains a separate architecture that is more reliant on unique scrip codes than alphabetical symbols. Building a generic scraper for the BSE requires a two-step process: code resolution and metadata harvesting.

### Scrip Code Resolution and Scrip Master

Every stock on the BSE is identified by a six-digit scrip code (e.g., 500325 for Reliance Industries). The scraper must either maintain a local lookup table or dynamically fetch the "Scrip Master" file provided by the BSE. The BSE website provides a master zip file containing the equity segment scrip codes, which can be programmatically downloaded and parsed.


|                      |                                            |
| -------------------- | ------------------------------------------ |
| **Attribute**        | **Value / Source**                         |
| **Scrip Master URL** | `www.bseindia.com -> Members -> SCRIP.ZIP` |
| **File Format**      | CSV (Comma Separated)                      |
| **Mapping Key**      | Scrip Code to Symbol/Company Name          |


### BSE Financials / Results Page URL (any scrip code)

The BSE "Get Quote" financials page supports a **scrip-code-only** URL. You do **not** need the company-name slug or short name to build the link:

| URL pattern | Example |
| ----------- | ------- |
| `https://www.bseindia.com/stock-share-price/equity/scripcode/{scrip_code}/financials-results/` | `.../equity/scripcode/513472/financials-results/` |
| Same base for annual reports | `.../equity/scripcode/{scrip_code}/financials-annual-reports` (if needed) |

So for **all** BSE equity scrip codes, the financials/results page URL is:

`https://www.bseindia.com/stock-share-price/equity/scripcode/<scrip_code>/financials-results/`

The human-readable SEO URL (e.g. `.../simplex-castings-ltd/simplexcas/513472/financials-results/`) is equivalent; the page content is the same. Use the `equity/scripcode/<scrip_code>` form when you only have the numeric scrip code.

### BSE Annual / Quarterly trend data (API)

The **Annual Trends** and **Quarterly Trends** tables on the financials-results page are loaded from:

`https://api.bseindia.com/BseIndiaAPI/api/GetReportNewFor_Result/w?scripcode={scrip_code}`

The response is JSON with HTML table strings: `AnninCr` (annual, in Crores), `QtlyinCr` (quarterly, in Cr.), and optionally `AnninM` / `QtlyinM` (in millions). **Origin** and **Referer** must both be `https://www.bseindia.com` (or `https://www.bseindia.com/`), otherwise the API may reject the request. Example:

```bash
curl 'https://api.bseindia.com/BseIndiaAPI/api/GetReportNewFor_Result/w?scripcode=513472' \
  -H 'origin: https://www.bseindia.com' \
  -H 'referer: https://www.bseindia.com/' \
  -H 'accept: application/json' \
  -H 'user-agent: Mozilla/5.0 ...'
```

The script `scripts/five_year_financial_table.py` uses this API for BSE: it parses `AnninCr` (or `AnninM`) into a table and prints/CSV/exports the annual trend.

### Utilizing the BSE API Subdomain

The BSE utilizes a specific subdomain for its API-driven services: `api.bseindia.com`. One of the most effective endpoints for retrieving historical corporate actions and links to financial filings is the Corporate Action endpoint.

The structure for the BSE Corporate Action API is:

`https://api.bseindia.com/BseIndiaAPI/api/CorporateAction/w?scripcode={scrip_code}`

This endpoint returns a JSON object containing several tables. `Table2` typically contains the chronological list of filings, including dates and categories. By iterating through this metadata, the scraper can identify the specific filing IDs for "Financial Results" or "Annual Reports," which are then used to construct the download URL for the corresponding XBRL instance document.

### Announcement Feed Scraping

To capture the last five years of data, the scraper must navigate the BSE's announcement archives. The BSE Corporate Announcement API allows for filtering by date range and category, though it often enforces a 365-day limit on individual queries. A script designed for a five-year window must implement a pagination loop, making five distinct requests (one for each year) to gather the full history of result filing links.

## Advanced XBRL Parsing for Statement Reconstruction

Once the scraper successfully identifies and downloads the XBRL filings (usually in `.xml` or `.zip` format), the technical challenge shifts to data normalization and reconstruction of the financial statements.

### Selecting the Python Parsing Stack

Parsing raw XBRL is more complex than standard XML because of the hierarchical relationships and contextual metadata. Several Python libraries are optimized for this:

- **python-xbrl**: A library built on `beautifulsoup4` and `lxml` that converts XBRL instance documents into a basic object model. It supports the extraction of DEI (Document and Entity Information) and can be extended with GAAP-specific serializers.
- **Arelle**: An open-source, industrial-strength XBRL processor. It is more complex to set up but provides comprehensive validation and the ability to convert XBRL filings into a JSON-OIM format, which is much easier for a Python script to process into a DataFrame.
- **EdgarTools (Conceptual Model)**: While primarily focused on US SEC filings, the `EdgarTools` methodology of "XBRL Stitching" is the ideal strategy for the Indian market. This involves aligning multiple years of filings to account for comparative figures often reported alongside current year data.

### Taxonomy Tag Mapping for Three Key Tables

To build the P&L, Balance Sheet, and Cash Flow tables, the script must map the Indian Ind AS taxonomy tags to consistent internal keys. The following table highlights the essential mapping required for a generic scraper to satisfy the five-year requirement.


|                   |                         |                                            |
| ----------------- | ----------------------- | ------------------------------------------ |
| **Statement**     | **Target Line Item**    | **Ind AS XBRL Taxonomy Tag (Typical)**     |
| **P&L Statement** | Revenue from Operations | `RevenueFromOperations`                    |
| **P&L Statement** | Net Profit/Loss         | `ProfitLoss` or `ProfitLossForPeriod`      |
| **P&L Statement** | Employee Benefits       | `EmployeeBenefitExpense`                   |
| **Balance Sheet** | Total Assets            | `Assets`                                   |
| **Balance Sheet** | Cash and Bank           | `CashAndCashEquivalents`                   |
| **Balance Sheet** | Accounts Receivable     | `TradeReceivables`                         |
| **Cash Flow**     | Operating Cash Flow     | `NetCashFlowFromUsedInOperatingActivities` |
| **Cash Flow**     | Investing Cash Flow     | `NetCashFlowFromUsedInInvestingActivities` |
| **Cash Flow**     | Financing Cash Flow     | `NetCashFlowFromUsedInFinancingActivities` |


### The Logic of "XBRL Stitching" for a 5-Year Table

A significant insight for constructing a five-year table is that a single annual XBRL filing typically contains data for two periods: the current reporting year and the prior comparative year. Therefore, a script targeting a five-year window only needs to successfully download and parse three annual filings (e.g., FY24, FY22, and FY20) to cover all five years.

The stitching logic involves:

1. **Extracting Facts**: Pulling all values associated with the desired tags across all contexts.
2. **Filtering Contexts**: Using the `period` and `startDate`/`endDate` elements to categorize facts into their respective financial years.
3. **Conflict Resolution**: When multiple filings report data for the same year (e.g., FY23 data in both the FY23 and FY24 filings), the script should prioritize the "Current Year" facts from the more recent filing, as they may include restatements or audit adjustments.

## Implementation Workflow: The Sequential Script Architecture

The proposed strategy is best implemented as a modular Python script. This ensures that the engine is generic enough to be applied to any stock by simply passing the ticker as an argument.

### Step 1: Initialization and Master Data Management

The script begins by loading or updating the scrip master data to facilitate NSE-to-BSE symbol cross-referencing. This allows the user to input "RELIANCE" and have the script automatically understand it needs to look for "RELIANCE" on NSE and "500325" on BSE.

### Step 2: Session Warming and Metadata Fetching

The script initializes a `requests.Session()` object, performs the NSE/BSE handshake, and queries the announcement APIs. It specifically looks for `Category: Financial Results` and filters for filings that have the "XBRL" indicator.

### Step 3: Automated File Acquisition

Using the filing URLs gathered in Step 2, the script downloads the instance documents. A robust implementation will store these in a local cache (e.g., a `data/raw_xbrl/` directory) to avoid redundant network calls and to respect the exchanges' rate limits.

### Step 4: Statement Parsing and Fact Extraction

The script passes each downloaded file to the XBRL parser. The parser iterates through the three statements (Balance Sheet, P&L, Cash Flow), extracting values based on the pre-defined taxonomy mapping. It must handle the "Unit" scaling—multiplying values by the reported scale to ensure all numbers are in standard INR (or the same scale, like Crores).

### Step 5: Normalization and Longitudinal Stitching

Using the "period" metadata, the script aligns the extracted facts into a temporal matrix. This phase includes a validation step: the Balance Sheet must balance ($Assets = Liabilities + Equity$). If a mathematical inconsistency is found, the script should log a warning, mimicking the "calculation linkbase" validation performed by regulatory portals.

### Step 6: Tabular Formatting and Output

Finally, the script converts the stitched data into Pandas DataFrames. Each statement (P&L, BS, CF) is represented as a separate table, with the most recent financial year as the first column, extending back five years.


|                    |          |          |          |          |          |
| ------------------ | -------- | -------- | -------- | -------- | -------- |
| **Financial Year** | **2024** | **2023** | **2022** | **2021** | **2020** |
| **Revenue**        | 100,000  | 90,000   | 85,000   | 70,000   | 75,000   |
| **Expense**        | 80,000   | 75,000   | 72,000   | 60,000   | 62,000   |
| **Net Profit**     | 20,000   | 15,000   | 13,000   | 10,000   | 13,000   |


## Operationalizing the Scraper: Scalability and Maintenance

Maintaining a scraper of this complexity requires ongoing operational strategies to handle the "quirks" of exchange websites and the evolution of financial reporting standards.

### Handling Standalone vs. Consolidated Results

A key requirement for a professional scraper is the ability to toggle between Standalone and Consolidated data. Large Indian firms like Tata Motors or Reliance have vast networks of subsidiaries; their Standalone figures (parent only) look vastly different from their Consolidated figures (entire group). The scraper must identify the `consolidated_ind` or similar flag in the JSON metadata from the NSE/BSE and allow the user to specify which statement type they require.

### Rate Limiting and Circumvention Strategy

The NSE and BSE are known to implement IP-based rate limiting. To build a scraper as "good as screener," it must be able to fetch data for hundreds of stocks without being blocked.


|                                  |                                                                             |                                                                 |
| -------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **Technique**                    | **Implementation Detail**                                                   | **Advantage**                                                   |
| **Exponential Backoff**          | Adding `time.sleep(2 ** retry_count)` between failed requests.              | Prevents overwhelming the server during transient errors.       |
| **Cookie Rotation**              | Periodically re-executing the session handshake to refresh tracking IDs.    | Maintains the appearance of a fresh user session.               |
| **Local Caching**                | Implementing a hash-based file naming system for downloaded XBRLs.          | Reduces total request volume over time.                         |
| **Headless Browsing (Optional)** | Using Selenium with PhantomJS or Chrome Headless for the initial handshake. | Can bypass JS-based challenges that standard `requests` cannot. |


### Data Validation and Financial Reconciliations

To ensure the scraped data is reliable, the engine should implement fundamental accounting reconciliations. For example, the **Net Income** from the P&L statement must flow into the **Retained Earnings** on the Balance Sheet (minus dividends), and the **Closing Cash** from the Cash Flow Statement must equal the **Cash on Balance Sheet**. Discrepancies often indicate a parsing error in the XBRL context (e.g., pulling a Standalone Cash Flow figure for a Consolidated Balance Sheet).

## Future Outlook: The API-First Evolution of Indian Exchanges

The landscape of financial scraping in India is shifting toward more formal, albeit often paid, data products. The NSE, through its "Market Data Products" division, offers snapshots and real-time feeds for a substantial annual fee. However, the regulatory disclosure mandate for public companies ensures that XBRL filings remain a free, albeit technically challenging, source of fundamental data.

The strategy of building an independent harvesting engine—rather than scraping aggregators—future-proofs the system against legal challenges and changes in aggregator pricing models. By focusing on the direct regulatory source (XBRL), the script achieves a level of data sovereignty that allows for custom financial modeling, quantitative analysis, and institutional-grade reporting that is truly as good as, if not more flexible than, standard market screeners.

## Reference Implementation

A minimal Python script that builds a **basic 5-year financial table** from NSE or BSE is at `scripts/five_year_financial_table.py`. It uses the NSE results-comparision API (with session warming) and the BSE Corporate Action API to list filings; NSE path produces Revenue/PAT/EBITDA/EPS table directly; BSE path lists financial filing links (full table from BSE requires XBRL download and parsing as in the steps below).

## Sequential Summary of Technical Execution

For a developer to convert this strategy into a functional Python project, the following sequential path is recommended:

1. **Master Data Acquisition**: Download and parse the BSE Scrip Master to create a universal ticker-to-ID mapping.
2. **Session Engine Development**: Build a robust request handler that manages NSE cookies and mimics browser headers.
3. **Filings Metadata Harvest**: Implement a 5-year pagination loop to gather results filing links from the NSE and BSE announcement APIs.
4. **XBRL Instance Retrieval**: Download the.xml filings, prioritizing consolidated annual reports for longitudinal consistency.
5. **XBRL Semantic Extraction**: Use `python-xbrl` or `Arelle` to extract monetary facts, ensuring correct unit scaling and context alignment.
6. **Tabular Reconstruction**: Stitch the facts into P&L, Balance Sheet, and Cash Flow DataFrames, applying standard accounting validations to verify accuracy.

This structured approach ensures that the resulting engine is compliant with regulatory standards while providing the deep, five-year historical transparency required for sophisticated investment research in the Indian equities market