import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputDir = path.resolve("output");
const entries = await fs.readdir(outputDir);
const workbookName = entries.find((name) => name.endsWith(".xlsx"));
if (!workbookName) throw new Error("No xlsx output found");

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(outputDir, workbookName)));
const sheetInfo = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 5000 });
console.log(sheetInfo.ndjson);
const previewDir = path.join(outputDir, "previews");
await fs.mkdir(previewDir, { recursive: true });
for (const sheet of workbook.worksheets.items) {
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
  const safeName = sheet.name.replaceAll(/[^0-9A-Za-z가-힣_-]/g, "_");
  await fs.writeFile(path.join(previewDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
  maxChars: 3000,
});
console.log(errors.ndjson);
