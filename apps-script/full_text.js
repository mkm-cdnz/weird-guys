function extractTextFromUrls() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var logSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("logs");

  // Get header row (first row) to determine column indexes dynamically
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];

  var urlIndex = headers.indexOf("url") + 1;  // Find "url" column
  var textIndex = headers.indexOf("full_text") + 1;  // Find "full_text" column
  var charCountIndex = headers.indexOf("char_count") + 1;  // Find "char_count" column

  // Ensure required columns exist; if not, create them
  if (urlIndex === 0 || textIndex === 0 || charCountIndex === 0) {
    Logger.log("Missing required columns: url, full_text, or char_count. Creating missing columns...");
    if (urlIndex === 0) {
      urlIndex = headers.length + 1;
      sheet.getRange(1, urlIndex).setValue("url");
    }
    if (textIndex === 0) {
      textIndex = headers.length + 2;
      sheet.getRange(1, textIndex).setValue("full_text");
    }
    if (charCountIndex === 0) {
      charCountIndex = headers.length + 3;
      sheet.getRange(1, charCountIndex).setValue("char_count");
    }
  }

  var lastRow = sheet.getLastRow();
  var urls = sheet.getRange(2, urlIndex, lastRow - 1, 1).getValues();
  var existingTexts = sheet.getRange(2, textIndex, lastRow - 1, 1).getValues();

  // Prepare log entries
  var logEntries = [];

  urls.forEach((row, index) => {
    var url = row[0];
    var fullText = existingTexts[index][0];
    var rowIndex = index + 2;

    if (!url) return;

    if (fullText) {
      logEntries.push([new Date(), `Skipped URL at row ${rowIndex} (Already processed)`]);
      return;
    }

    try {
      var response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
      var html = response.getContentText();
      var cleanText = extractCleanText(html);

      var truncatedText = cleanText.substring(0, 50000);
      var charCount = truncatedText.length;

      sheet.getRange(rowIndex, textIndex).setValue(truncatedText);
      sheet.getRange(rowIndex, charCountIndex).setValue(charCount);

      logEntries.push([new Date(), `Extracted text for row ${rowIndex} (${charCount} chars)`]);

    } catch (e) {
      logEntries.push([new Date(), `Error fetching URL at row ${rowIndex}: ${e.message}`]);
    }
  });

  // Log results in "logs" tab
  if (logEntries.length > 0) {
    logSheet.getRange(logSheet.getLastRow() + 1, 1, logEntries.length, 2).setValues(logEntries);
  }
}

// Function to clean extracted text by removing HTML tags
function extractCleanText(html) {
  html = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ""); 
  html = html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ""); 
  html = html.replace(/<[^>]+>/g, " "); 

  return html.replace(/\s+/g, " ").trim();
}

