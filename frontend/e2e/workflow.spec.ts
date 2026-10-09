import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Exercise the deployed same-origin proxy for both browser and API assertions.
const API = "http://localhost:3010/api";
async function register(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await page.getByLabel("Full name").fill("Synthetic Reviewer");
  await page.getByLabel("Work email").fill(`browser-${Date.now()}-${Math.random().toString(16).slice(2)}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill("Synthetic-test-password-93!");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  const session = await (await page.request.get(`${API}/auth/session`)).json();
  const organization = await page.request.post(`${API}/organizations/`, { data: { name: `Synthetic Browser Bank ${Date.now()}` }, headers: { "X-CSRF-Token": session.csrf_token } });
  expect(organization.status()).toBe(201);
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Organization" }).locator("option")).toHaveCount(1);
}

test("sign-in is accessible and unauthenticated API access is denied", async ({ page, request }) => {
  await page.goto("/");
  expect((await request.get(`${API}/organizations/`)).status()).toBe(401);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Work email")).toBeFocused();
});

test("private intake, actual worker extraction fixture, source and approval persist", async ({ page }) => {
  test.setTimeout(120000);
  await register(page);
  await page.getByRole("button", { name: "Regulatory library", exact: true }).click();
  await page.getByLabel("Regulation title").fill("Synthetic capital review requirement");
  await page.getByLabel("Source document").setInputFiles({ name: "synthetic.txt", mimeType: "text/plain", buffer: Buffer.from("Section 1\nThe synthetic bank shall review its capital ratio daily.") });
  await page.getByRole("button", { name: "Upload and extract obligations" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Processing finished" })).toBeVisible({ timeout: 45000 });
  await page.getByRole("button", { name: "Compliance matrix", exact: true }).click();
  await expect(page.getByText("pending_review · uncertain", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Review source", exact: true }).click();
  await expect(page.locator("blockquote")).toContainText("synthetic bank shall");
  await page.getByRole("button", { name: "Approve obligation", exact: true }).click();
  await expect(page.getByText("approved · applicable", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Control library", exact: true }).click();
  await page.getByLabel("Control code", { exact: true }).fill("CTL-SYNTHETIC-DAILY");
  await page.getByLabel("Control objective", { exact: true }).fill("Review the synthetic capital ratio daily");
  await page.getByLabel("Control procedure", { exact: true }).fill("Calculate, inspect and record the daily synthetic ratio.");
  await page.getByRole("button", { name: "Create control proposal", exact: true }).click();
  await page.getByRole("button", { name: "Approve control CTL-SYNTHETIC-DAILY", exact: true }).click();
  await page.getByRole("combobox", { name: "Reviewed obligation", exact: true }).selectOption({ label: "The synthetic bank shall review its capital ratio daily." });
  await page.getByRole("combobox", { name: "Reviewed control", exact: true }).selectOption({ label: "CTL-SYNTHETIC-DAILY" });
  await page.getByLabel("Mapping rationale", { exact: true }).fill("The reviewed control performs the required daily ratio review.");
  await page.getByRole("button", { name: "Propose mapping", exact: true }).click();
  await page.getByRole("combobox", { name: "Evidence control", exact: true }).selectOption({ label: "CTL-SYNTHETIC-DAILY" });
  await page.getByLabel("Evidence title", { exact: true }).fill("Synthetic daily ratio review log");
  await page.getByLabel("Evidence source", { exact: true }).setInputFiles({ name: "synthetic-evidence.txt", mimeType: "text/plain", buffer: Buffer.from("Daily synthetic capital ratio calculation and reviewer sign-off: passed.") });
  await page.getByRole("button", { name: "Upload private evidence", exact: true }).click();
  await page.getByRole("button", { name: "Inspect evidence source", exact: true }).click();
  await expect(page.locator(".source-review pre")).toContainText("reviewer sign-off");
  await page.getByRole("combobox", { name: "Evidence decision", exact: true }).selectOption("valid");
  await page.getByLabel("Evidence review notes", { exact: true }).fill("Synthetic private source inspected and covers this control.");
  await page.getByRole("button", { name: "Save evidence review", exact: true }).click();
  await page.getByRole("combobox", { name: "Test control", exact: true }).selectOption({ label: "CTL-SYNTHETIC-DAILY" });
  await page.getByRole("combobox", { name: "Test result", exact: true }).selectOption("pass");
  await page.getByLabel("Effectiveness score", { exact: true }).fill("0.95");
  await page.getByLabel("Test findings", { exact: true }).fill("Human reviewer verified the synthetic evidence and procedure.");
  await page.getByRole("button", { name: "Record reviewed test", exact: true }).click();
  await expect(page.getByText("pass · approved", { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Compliance matrix", exact: true }).click();
  await page.getByRole("button", { name: "Approve mapping", exact: true }).click();
  await expect(page.getByText("Mapping reviewed", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Assess gaps", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: /Job .* succeeded/ })).toBeVisible({ timeout: 45000 });
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(["regulaai.organization-id"]);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({ path: "../output/playwright/review-workflow.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
});

test("invalid upload is rejected and cookie mutations require CSRF", async ({ page }) => {
  await register(page);
  const denied = await page.request.post(`${API}/organizations/`, { data: { name: "CSRF rejected" } });
  expect(denied.status()).toBe(403);
  await page.getByRole("button", { name: "Regulatory library", exact: true }).click();
  await page.getByLabel("Regulation title").fill("Invalid source test");
  await page.getByLabel("Source document").setInputFiles({ name: "invalid.pdf", mimeType: "application/pdf", buffer: Buffer.from("This is not a PDF") });
  await page.getByRole("button", { name: "Upload and extract obligations" }).click();
  await expect(page.locator(".form-error[role=alert]")).toContainText("not a valid PDF");
});

test("another browser tenant cannot list the first tenant's workspace", async ({ page, browser }) => {
  await register(page);
  const organizationId = await page.getByRole("combobox", { name: "Organization" }).inputValue();
  const context = await browser.newContext();
  try {
    const other = await context.newPage();
    await register(other);
    const response = await other.request.get(`${API}/regulations/?organization_id=${organizationId}`);
    expect(response.status()).toBe(403);
  } finally { await context.close(); }
});

test("terminal model-adapter failure is visible and retry creates a new job", async ({ page }) => {
  await register(page);
  await page.getByRole("button", { name: "Regulatory library", exact: true }).click();
  await page.getByLabel("Regulation title").fill("Failure fixture");
  await page.getByLabel("Source document").setInputFiles({ name: "failure.txt", mimeType: "text/plain", buffer: Buffer.from("This source deliberately has no supported extraction fixture.") });
  await page.getByRole("button", { name: "Upload and extract obligations" }).click();
  await expect(page.getByRole("button", { name: "Retry failed job" })).toBeVisible({ timeout: 45000 });
  const previous = await page.getByRole("status").filter({ hasText: /^Job / }).textContent();
  await page.getByRole("button", { name: "Retry failed job" }).click();
  await expect(page.getByRole("status").filter({ hasText: /^Job / })).not.toHaveText(previous ?? "");
});
