import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  preview: {
    allowedHosts: ["truthful-freedom-production-a51b718f.up.railway.app"],
  },
});
