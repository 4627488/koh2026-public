import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { execSync } from "node:child_process";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

function getGitShortSha(): string {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
}

function isGitDirty(): boolean {
    return execSync("git status --porcelain --untracked-files=normal", {
        encoding: "utf8",
    }).trim().length > 0;
}

function getAppVersion(): string {
    if (process.env.VITE_APP_VERSION) return process.env.VITE_APP_VERSION;
    try {
        const shortSha = getGitShortSha();
        return isGitDirty() ? `${shortSha}-dirty` : shortSha;
    } catch {
        return "dev";
    }
}

export default defineConfig(({ command }) => ({
    define: {
        __APP_VERSION__: JSON.stringify(getAppVersion()),
    },
    plugins: [react()],
    base: command === "build" ? "/static/app/" : "/",
    resolve: {
        alias: {
            "@": fileURLToPath(new URL("./src", import.meta.url)),
        },
    },
    server: {
        port: 5173,
        host: process.env.VITE_HOST ?? "localhost",
        proxy: {
            "/api": { target: BACKEND, changeOrigin: true },
            "/ws":  { target: BACKEND.replace(/^http/, "ws"), ws: true },
        },
    },
    build: {
        outDir: "../src/koh/static/app",
        emptyOutDir: true,
        sourcemap: false,
        cssCodeSplit: false,
        rollupOptions: {
            output: {
                entryFileNames: "assets/[name]-[hash].js",
                chunkFileNames: "assets/[name]-[hash].js",
                assetFileNames: "assets/[name]-[hash][extname]",
            },
        },
    },
}));
