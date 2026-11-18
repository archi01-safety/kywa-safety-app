import { expect, test } from "@playwright/test";

test("cached navigation skips redundant reads and manual refresh gets current records", async ({page}) => {
  test.skip(!!process.env.ORGANIZATION_ID && process.env.ORGANIZATION_ID !== "kywa");
  let lists = 0, charts = 0;
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") return;
    if (path.endsWith("/api/assessments")) lists++;
    if (path.endsWith("/api/overview")) charts++;
  });
  const menu = (name: string) => page.getByRole("button", {name, exact: true});
  await page.goto("/#actions");
  await menu("관리자로 체험하기").click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.locator(".record-item").first()).toBeVisible();
  const firstLists = lists;
  await menu("AI 위험성평가").click();
  await expect(page.locator(".overview-charts")).toBeVisible();
  const firstCharts = charts;
  await menu("개선조치 · 재평가").click();
  await expect(page.locator(".record-item").first()).toBeVisible();
  await menu("AI 위험성평가").click();
  await expect(page.locator(".overview-charts")).toBeVisible();
  expect(lists).toBe(firstLists);
  expect(charts).toBe(firstCharts);
  await menu("개선조치 · 재평가").click();
  await Promise.all([
    page.waitForResponse(r => new URL(r.url()).pathname.endsWith("/api/assessments") && r.ok()),
    menu("목록 새로고침").click(),
  ]);
  expect(lists).toBe(firstLists + 1);
});
