import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
const release = JSON.parse(readFileSync(new URL("../backend/app/release.json", import.meta.url), "utf8"));
function git(args: string[], fallback: string) { try { return execFileSync("git", args, {encoding:"utf8", stdio:["ignore","pipe","ignore"]}).trim(); } catch { return fallback; } }
const build = {...release, revision:process.env.CAO_BUILD_REVISION || git(["rev-parse","HEAD"],"unknown"),
  built_at:process.env.CAO_BUILD_DATE || new Date().toISOString(),
  source_state:process.env.CAO_SOURCE_STATE || (git(["status","--porcelain"],"unknown") === "unknown" ? "unknown" : git(["status","--porcelain"],"unknown") ? "dirty" : "clean")};
export default defineConfig({
  base: process.env.VITE_PUBLIC_BASE_PATH || "/",
  define: { __APP_BUILD__: JSON.stringify(build) },
  plugins: [react()]
});
