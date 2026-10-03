import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", timeout: 60000, fullyParallel: true, workers: 2,
  reporter: "list",
  use: {baseURL: process.env.TEST_BASE_URL || "http://localhost:3000", channel: process.env.PLAYWRIGHT_CHANNEL || "msedge", screenshot: "only-on-failure", trace: "retain-on-failure"},
  projects: [
    {name: "desktop", use: {viewport: {width: 1440, height: 1000}}},
    {name: "tablet", use: {viewport: {width: 834, height: 1112}}},
    {name: "mobile", use: {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}},
  ],
});
