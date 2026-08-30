import { expect, test, type Page, type Route } from "@playwright/test";

const project = {
  project_id: "project-1",
  name: "Default workspace",
  selection_id: "selection-1",
  selected_count: 3,
  data_loaded: true,
};

const workflow = {
  stages: {
    metadata_builder: { status: "complete", metadata_selection_id: "selection-1" },
    univariate_statistics: { status: "ready" },
    bivariate_statistics: { status: "ready" },
    multivariate_statistics: { status: "ready" },
  },
  process_overview: {
    metadata_downloaded_isins: 3,
    metadata_builder_isins: 3,
    univariate_statistics_isins: 3,
  },
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installSingleWorkspaceApi(page: Page): Promise<string[]> {
  const calls: string[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    calls.push(`${method} ${path}`);

    if (method === "GET" && path === "/api/project-context") {
      return json(route, {
        current_project_id: project.project_id,
        current_project: project,
        projects: [project],
      });
    }
    if (method === "GET" && path === `/api/projects/${project.project_id}/workflow`) {
      return json(route, workflow);
    }
    if (method === "GET" && path === "/api/workflow") return json(route, workflow);

    // Page-level requests are intentionally not business fixtures here: this regression suite
    // owns the frozen shell/routing contract only. A typed 404 keeps the page mounted while
    // proving navigation itself does not mutate workspace identity.
    return json(route, { detail: { code: "not_available_in_shell_fixture" } }, 404);
  });
  return calls;
}

test("legacy shell exposes exactly the four canonical single-workspace routes", async ({ page }) => {
  const calls = await installSingleWorkspaceApi(page);
  await page.goto("/metadata");

  const navigation = page.getByRole("navigation", { name: "Workflow" });
  await expect(navigation).toBeVisible();
  await expect(page.locator("#current-project")).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: /project/i })).toHaveCount(0);

  const links = navigation.getByRole("link");
  await expect(links).toHaveCount(4);
  await expect(links.nth(0)).toHaveAttribute("href", "/metadata");
  await expect(links.nth(1)).toHaveAttribute("href", "/univariate");
  await expect(links.nth(2)).toHaveAttribute("href", "/bivariate");
  await expect(links.nth(3)).toHaveAttribute("href", "/multivariate");

  const navigationCount = await page.evaluate(() => performance.getEntriesByType("navigation").length);
  await links.nth(1).click();
  await expect(page).toHaveURL(/\/univariate$/);
  await expect.poll(() => page.evaluate(() => performance.getEntriesByType("navigation").length)).toBe(navigationCount);
  await page.getByRole("link", { name: /Bivariate/ }).click();
  await expect(page).toHaveURL(/\/bivariate$/);
  await page.getByRole("link", { name: /Multivariate/ }).click();
  await expect(page).toHaveURL(/\/multivariate$/);
  await page.getByRole("link", { name: /Metadata/ }).click();
  await expect(page).toHaveURL(/\/metadata$/);

  expect(calls).not.toContain("PUT /api/project-context/current-project");
});

test("legacy project-prefixed and old route names are no longer browser authorities", async ({ page }) => {
  await installSingleWorkspaceApi(page);

  await page.goto("/metadata-builder");
  await expect(page.getByRole("navigation", { name: "Workflow" }).getByRole("link").nth(0)).toHaveAttribute("href", "/metadata");
  await expect(page.locator("#current-project")).toHaveCount(0);

  await page.goto("/projects/legacy/univariate-statistics");
  await expect(page.getByRole("navigation", { name: "Workflow" }).getByRole("link").nth(0)).toHaveAttribute("href", "/metadata");
  await expect(page.locator("#current-project")).toHaveCount(0);
});

test("mobile shell opens and closes workflow navigation without a project selector", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installSingleWorkspaceApi(page);
  await page.goto("/metadata");

  const navigation = page.locator("#project-navigation-drawer");
  await page.getByRole("button", { name: "Open workflow navigation" }).click();
  await expect(navigation).toHaveAttribute("data-open", "true");
  await expect(page.locator("#current-project")).toHaveCount(0);

  const backdrop = page.getByRole("button", { name: "Close workflow navigation" });
  const box = await backdrop.boundingBox();
  if (!box) throw new Error("workflow navigation backdrop has no clickable area");
  await page.mouse.click(box.x + box.width - 8, box.y + box.height / 2);
  await expect(navigation).toHaveAttribute("data-open", "false");
});
