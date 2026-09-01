// Build a MarkdownDB SQLite index over the Markdown corpus.
// Run:  node mddb/build.mjs
// Produces: data/stores/markdown.db  (read directly by the Python app)
import { MarkdownDB } from "mddb";

const client = new MarkdownDB({
  client: "sqlite3",
  connection: { filename: "data/stores/markdown.db" },
});

await client.init();
await client.indexFolder({ folderPath: "data/markdown" });
console.log("MarkdownDB index built at data/stores/markdown.db");
process.exit(0);
