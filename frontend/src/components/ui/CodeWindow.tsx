import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import {
  createHighlighterCore,
  type HighlighterCore,
  type LanguageRegistration,
  type ThemeRegistration,
} from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";
import { IconKey } from "./IconKey";

const languageByExtension: Record<string, string> = {
  c: "c",
  cpp: "c",
  css: "css",
  go: "go",
  h: "c",
  html: "html",
  java: "java",
  js: "javascript",
  jsx: "jsx",
  json: "json",
  md: "markdown",
  mdx: "mdx",
  py: "python",
  rs: "rust",
  sh: "bash",
  sql: "sql",
  ts: "typescript",
  tsx: "tsx",
  yaml: "yaml",
  yml: "yaml",
};

const languageLoaders: Record<string, () => Promise<LanguageRegistration[]>> = {
  bash: () => import("@shikijs/langs/bash").then((module) => module.default),
  c: () => import("@shikijs/langs/c").then((module) => module.default),
  css: () => import("@shikijs/langs/css").then((module) => module.default),
  go: () => import("@shikijs/langs/go").then((module) => module.default),
  html: () => import("@shikijs/langs/html").then((module) => module.default),
  java: () => import("@shikijs/langs/java").then((module) => module.default),
  javascript: () => import("@shikijs/langs/javascript").then((module) => module.default),
  jsx: () => import("@shikijs/langs/jsx").then((module) => module.default),
  json: () => import("@shikijs/langs/json").then((module) => module.default),
  markdown: () => import("@shikijs/langs/markdown").then((module) => module.default),
  mdx: () => import("@shikijs/langs/mdx").then((module) => module.default),
  python: () => import("@shikijs/langs/python").then((module) => module.default),
  rust: () => import("@shikijs/langs/rust").then((module) => module.default),
  sql: () => import("@shikijs/langs/sql").then((module) => module.default),
  typescript: () => import("@shikijs/langs/typescript").then((module) => module.default),
  tsx: () => import("@shikijs/langs/tsx").then((module) => module.default),
  yaml: () => import("@shikijs/langs/yaml").then((module) => module.default),
};

const themeLoaders: Record<"light" | "dark", () => Promise<ThemeRegistration>> = {
  dark: () => import("@shikijs/themes/github-dark").then((module) => module.default),
  light: () => import("@shikijs/themes/github-light").then((module) => module.default),
};

const highlighterCache = new Map<string, Promise<HighlighterCore>>();

function getHighlighter(language: string, theme: "light" | "dark") {
  const key = `${language}:${theme}`;
  let highlighter = highlighterCache.get(key);
  if (!highlighter) {
    const languageLoader = languageLoaders[language];
    if (!languageLoader) return Promise.reject(new Error(`Unsupported syntax highlighting language: ${language}`));
    highlighter = Promise.all([languageLoader(), themeLoaders[theme]()]).then(([langs, themeRegistration]) =>
      createHighlighterCore({
        themes: [themeRegistration],
        langs,
        engine: createJavaScriptRegexEngine(),
      })
    );
    highlighterCache.set(key, highlighter);
  }
  return highlighter;
}

interface CodeWindowProps {
  code: string;
  path: string;
  startLine?: number;
  highlightRange?: [number, number];
  theme: "light" | "dark";
}

export function CodeWindow({ code, path, startLine = 1, highlightRange, theme }: CodeWindowProps) {
  const [lines, setLines] = useState<Array<Array<{ content: string; color?: string }>> | null>(null);
  const [highlightError, setHighlightError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const extension = path.split(".").pop()?.toLowerCase() ?? "";
  const language = languageByExtension[extension];

  useEffect(() => {
    if (!language) {
      setLines(null);
      setHighlightError(null);
      return;
    }
    let active = true;
    setHighlightError(null);
    void getHighlighter(language, theme)
      .then((highlighter) => highlighter.codeToTokens(code, {
        lang: language,
        theme: theme === "dark" ? "github-dark" : "github-light",
      }))
      .then((result) => {
        if (active) setLines(result.tokens);
      })
      .catch((cause: unknown) => {
        if (active) {
          setHighlightError(cause instanceof Error ? cause.message : "Syntax highlighting is unavailable.");
          setLines(null);
        }
      });
    return () => {
      active = false;
    };
  }, [code, language, theme]);

  const copyCode = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const rawLines = code.split("\n");
  const renderedLines: Array<Array<{ content: string; color?: string }>> =
      lines ?? rawLines.map((line) => [{ content: line }]);

  return (
    <section className="overflow-hidden rounded-lg border border-edge bg-glass text-glass-ink" aria-label={`Source file ${path}`}>
      <header className="flex items-center justify-between border-b border-glass-ink/20 bg-glass px-3 py-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-xs">{path}</p>
          <p className="font-mono text-[10px] text-glass-ink/70">
            {language ?? "plain text"} · {rawLines.length} lines · Verified source
          </p>
        </div>
        <IconKey label={copied ? "Code copied" : "Copy code"} variant="ghost" onClick={() => void copyCode()}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </IconKey>
      </header>
      {highlightError && <p role="status" className="border-b border-edge px-3 py-1 text-xs text-led-amber">Syntax highlighting unavailable: {highlightError}</p>}
      <pre className="max-h-[65vh] overflow-auto py-3 text-xs leading-6">
        <code>
          {renderedLines.map((tokens, index) => {
            const lineNumber = startLine + index;
            const isHighlighted = highlightRange
              ? lineNumber >= highlightRange[0] && lineNumber <= highlightRange[1]
              : false;
            return (
              <span
                key={`${lineNumber}-${index}`}
                className={`block min-w-max px-3 ${isHighlighted ? "bg-led-amber/15" : ""}`}
              >
                <span className="mr-4 inline-block w-10 select-none text-right text-glass-ink/45" aria-hidden="true">
                  {lineNumber}
                </span>
                {tokens.map((token, tokenIndex) => (
                  <span key={tokenIndex} style={token.color ? { color: token.color } : undefined}>
                    {token.content}
                  </span>
                ))}
              </span>
            );
          })}
        </code>
      </pre>
    </section>
  );
}
