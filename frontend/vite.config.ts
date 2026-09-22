import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: process.env.VITE_PUBLIC_BASE_PATH || "/",
  plugins: [react()]
});
