import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { buttonInteractionManifest } from "./button-interaction-manifest";

const sourceRoot = resolve(process.cwd(), "src");
const productionSources = ["pages/metadata-builder.tsx", "pages/univariate-statistics.tsx", "pages/bivariate-statistics.tsx", "pages/multivariate-statistics.tsx", "shell/frame.tsx"];

test("every interaction-manifest control is unique and declared in production UI source", async () => {
  const source = (await Promise.all(productionSources.map((file) => readFile(resolve(sourceRoot, file), "utf8")))).join("\n");
  const manifestControls = buttonInteractionManifest.length;

  expect(manifestControls).toBeGreaterThan(0);
  expect(new Set(buttonInteractionManifest.map((entry) => `${entry.route}:${entry.state}:${entry.role}:${entry.name}`)).size).toBe(manifestControls);
  for (const control of buttonInteractionManifest) expect(source).toContain(control.name);
});
