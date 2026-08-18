export class JsonDataRepository {
  constructor(root = "/data/demo") {
    this.root = root.replace(/\/$/, "");
    this.cache = new Map();
  }

  async getJson(path) {
    const url = path.startsWith("/") ? path : `${this.root}/${path}`;
    if (!this.cache.has(url)) {
      this.cache.set(url, fetch(url).then(async response => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`);
        return response.json();
      }));
    }
    return this.cache.get(url);
  }

  getProfile(personId) {
    return this.getJson(`${personId}/profile.json`);
  }

  getManifest(personId) {
    return this.getJson(`${personId}/manifest.json`);
  }

  getWeeklySummary(personId, domain, taskId = null) {
    const filename = taskId ? `${taskId}-weekly-summary.json` : "weekly-summary.json";
    return this.getJson(`${personId}/${domain}/${filename}`);
  }

  getWeekDetail(personId, domain, weekId, taskId = null) {
    const taskPath = taskId ? `${taskId}/` : "";
    return this.getJson(`${personId}/${domain}/weeks/${taskPath}${weekId}.json`);
  }
}
