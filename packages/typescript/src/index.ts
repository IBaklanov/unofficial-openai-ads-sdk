import { z } from "zod";

export interface OpenAIAdsOptions {
  apiKey?: string;
  baseURL?: string;
  timeoutMs?: number;
  maxRetries?: number;
  fetch?: typeof fetch;
  defaultHeaders?: Record<string, string>;
}

export interface RequestOptions {
  query?: Record<string, unknown>;
  body?: unknown;
  formData?: FormData;
  responseSchema?: z.ZodTypeAny;
  timeoutMs?: number;
  maxRetries?: number;
  idempotencyKey?: string;
  retryNonIdempotent?: boolean;
  signal?: AbortSignal;
}

export class OpenAIAdsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OpenAIAdsError";
  }
}

export class ValidationError extends OpenAIAdsError {
  constructor(message: string, readonly cause?: unknown) {
    super(message);
    this.name = "ValidationError";
  }
}

export class TimeoutError extends OpenAIAdsError {
  constructor(message = "OpenAI Ads request timed out") {
    super(message);
    this.name = "TimeoutError";
  }
}

export class APIError extends OpenAIAdsError {
  constructor(
    message: string,
    readonly status: number,
    readonly response: Response,
    readonly body: unknown,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

export class AuthenticationError extends APIError {
  constructor(response: Response, body: unknown, requestId?: string) {
    super("OpenAI Ads authentication failed", response.status, response, body, requestId);
    this.name = "AuthenticationError";
  }
}

export class RateLimitError extends APIError {
  constructor(response: Response, body: unknown, requestId?: string) {
    super("OpenAI Ads rate limit exceeded", response.status, response, body, requestId);
    this.name = "RateLimitError";
  }
}

export class APIClient {
  readonly baseURL: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly fetchImpl: typeof fetch;
  private readonly defaultHeaders: Record<string, string>;

  constructor(options: OpenAIAdsOptions = {}) {
    const apiKey = options.apiKey ?? process.env.OPENAI_ADS_API_KEY;
    if (!apiKey) throw new ValidationError("OpenAI Ads API key is required. Pass apiKey or set OPENAI_ADS_API_KEY.");
    this.apiKey = apiKey;
    this.baseURL = options.baseURL ?? "https://api.ads.openai.com/v1";
    this.timeoutMs = options.timeoutMs ?? 60_000;
    this.maxRetries = options.maxRetries ?? 2;
    this.fetchImpl = options.fetch ?? fetch;
    this.defaultHeaders = options.defaultHeaders ?? {};
  }

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const maxRetries = options.maxRetries ?? this.maxRetries;
    const canRetryBody = method === "GET" || options.retryNonIdempotent === true || Boolean(options.idempotencyKey);
    let attempt = 0;
    let lastError: unknown;
    while (attempt <= maxRetries) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? this.timeoutMs);
      const signal = mergeSignals(controller.signal, options.signal);
      try {
        const init: RequestInit = { method, headers: this.headers(options), signal };
        if (options.formData) init.body = options.formData;
        else if (options.body !== undefined) init.body = JSON.stringify(options.body);
        const response = await this.fetchImpl(this.buildURL(path, options.query), init);
        clearTimeout(timeout);
        const parsed = await parseJSON(response);
        if (response.ok) {
          return (options.responseSchema ? options.responseSchema.parse(parsed) : parsed) as T;
        }
        if (shouldRetry(response.status) && canRetryBody && attempt < maxRetries) {
          await sleep(retryAfterMs(response.headers.get("retry-after")) ?? backoffMs(attempt));
          attempt += 1;
          continue;
        }
        throw toAPIError(response, parsed);
      } catch (error) {
        clearTimeout(timeout);
        if (error instanceof z.ZodError) throw new ValidationError("OpenAI Ads response failed validation", error);
        if (error instanceof APIError) throw error;
        if (isAbort(error)) {
          if (canRetryBody && attempt < maxRetries) {
            await sleep(backoffMs(attempt));
            attempt += 1;
            continue;
          }
          throw new TimeoutError();
        }
        lastError = error;
        if (canRetryBody && attempt < maxRetries) {
          await sleep(backoffMs(attempt));
          attempt += 1;
          continue;
        }
        throw error;
      }
    }
    throw lastError instanceof Error ? lastError : new Error("OpenAI Ads request failed");
  }

  private buildURL(path: string, query?: Record<string, unknown>): string {
    const url = new URL(`${this.baseURL.replace(/\/$/, "")}${path}`);
    appendQuery(url, query);
    return url.toString();
  }

  private headers(options: RequestOptions): Headers {
    const headers = new Headers(this.defaultHeaders);
    headers.set("authorization", `Bearer ${this.apiKey}`);
    if (!options.formData) headers.set("content-type", "application/json");
    if (options.idempotencyKey) headers.set("idempotency-key", options.idempotencyKey);
    return headers;
  }
}

const Status = z.enum(["active", "paused"]);
const MutableStatus = z.enum(["active", "paused", "archived"]);
const ListOrder = z.enum(["asc", "desc"]);
const CampaignBiddingType = z.enum(["impressions", "clicks"]);
const BillingEventType = z.enum(["impression", "click"]);
const ReviewStatus = z.enum(["in_review", "rejected", "approved"]);
const CreativeType = z.literal("chat_card");
const ListParams = z.object({ limit: z.number().int().min(1).max(10_000).optional(), after: z.string().optional(), before: z.string().optional(), order: ListOrder.optional() });
const Budget = z.object({ lifetime_spend_limit_micros: z.number().int().min(1_000_000) }).passthrough();
const TargetingLocations = z.object({ countries: z.array(z.string()).optional() }).passthrough();
const Targeting = z.object({ locations: TargetingLocations.optional(), excluded_locations: TargetingLocations.optional() }).passthrough();
const Campaign = z.object({
  id: z.string(),
  created_at: z.number(),
  updated_at: z.number(),
  name: z.string(),
  description: z.string().nullable().optional(),
  status: z.string(),
  start_time: z.number().nullable().optional(),
  end_time: z.number().nullable().optional(),
  budget: Budget,
  targeting: Targeting.optional().nullable(),
  bidding_type: CampaignBiddingType.optional(),
  mode: z.string().nullable().optional(),
  conversion_event_setting_ids: z.array(z.string()).optional(),
}).passthrough();
const CampaignCreateParams = z.object({
  name: z.string().min(3).max(1000).refine((v) => v.trim().length > 0, "name must contain a non-space character"),
  description: z.string().optional(),
  start_time: z.number().int().min(946684800).max(4102444800).optional(),
  end_time: z.number().int().min(946684800).max(4102444800).optional(),
  status: Status,
  budget: Budget,
  targeting: Targeting.optional(),
  bidding_type: CampaignBiddingType.optional(),
}).strict();
const CampaignUpdateParams = CampaignCreateParams.partial().extend({ status: MutableStatus.optional() }).strict();
const BiddingConfig = z.object({ billing_event_type: BillingEventType, max_bid_micros: z.number().int().min(1).max(100_000_000) }).strict();
const AdGroup = z.object({ id: z.string(), created_at: z.number(), updated_at: z.number(), name: z.string(), description: z.string().nullable().optional(), context_hints: z.array(z.string()).optional(), status: z.string(), bidding_config: BiddingConfig.passthrough() }).passthrough();
const AdGroupCreateParams = z.object({ campaign_id: z.string(), name: z.string().min(3).max(1000), description: z.string().optional(), context_hints: z.array(z.string()).optional(), status: Status, bidding_config: BiddingConfig }).strict();
const AdGroupUpdateParams = AdGroupCreateParams.omit({ campaign_id: true }).partial().extend({ status: MutableStatus.optional() }).strict();
const Creative = z.object({ type: CreativeType, title: z.string(), body: z.string(), target_url: z.string().optional(), file_id: z.string().optional(), image_url: z.string().optional() }).passthrough();
const CreativeParams = z.object({ type: CreativeType, title: z.string().min(3).max(50), body: z.string().max(100), target_url: z.string(), file_id: z.string() }).strict();
const UpdateCreativeParams = CreativeParams.partial().extend({ type: CreativeType }).strict();
const Ad = z.object({ id: z.string(), created_at: z.number(), updated_at: z.number(), ad_group_id: z.string().optional(), name: z.string(), status: z.string(), creative: Creative, review_status: ReviewStatus.optional(), appeal: z.unknown().optional() }).passthrough();
const AdCreateParams = z.object({ ad_group_id: z.string(), name: z.string().min(3).max(1000), status: Status, creative: CreativeParams }).strict();
const AdUpdateParams = AdCreateParams.omit({ ad_group_id: true }).partial().extend({ status: MutableStatus.optional(), creative: UpdateCreativeParams.optional() }).strict();
const UploadParams = z.object({ image_url: z.string().url().optional(), file: z.instanceof(Blob).optional() }).strict().refine((v) => Boolean(v.image_url) !== Boolean(v.file), "Provide exactly one of image_url or file.");
const Upload = z.object({ file_id: z.string() }).passthrough();
const AdAccount = z.object({ id: z.string(), name: z.string().optional(), url: z.string().optional(), preview_url: z.string().optional(), timezone: z.string().optional(), currency_code: z.string().optional() }).passthrough();
const DateRange = z.object({ since: z.string(), until: z.string() }).strict().refine((v) => !isFutureDate(v.until), "dateRange.until cannot be in the future");
const InsightsParams = z.object({
  timeGranularity: z.enum(["daily", "none"]).optional(),
  aggregationLevel: z.enum(["ad_account", "campaign", "ad_group", "ad"]).optional(),
  limit: z.number().int().min(1).max(10_000).optional(),
  before: z.string().optional(),
  after: z.string().optional(),
  dateRange: DateRange.optional(),
  fields: z.array(z.string()).optional(),
  filters: z.array(z.string()).optional(),
  sort: z.array(z.string()).optional(),
}).strict();
const Insight = z.object({ id: z.string().nullable().optional(), start_time: z.string().or(z.number()).optional(), end_time: z.string().or(z.number()).optional() }).passthrough();

export type Campaign = z.infer<typeof Campaign>;
export type CampaignCreateParams = z.infer<typeof CampaignCreateParams>;
export type CampaignUpdateParams = z.infer<typeof CampaignUpdateParams>;
export type AdGroup = z.infer<typeof AdGroup>;
export type AdGroupCreateParams = z.infer<typeof AdGroupCreateParams>;
export type AdGroupUpdateParams = z.infer<typeof AdGroupUpdateParams>;
export type Ad = z.infer<typeof Ad>;
export type AdCreateParams = z.infer<typeof AdCreateParams>;
export type AdUpdateParams = z.infer<typeof AdUpdateParams>;
export type Upload = z.infer<typeof Upload>;
export type AdAccount = z.infer<typeof AdAccount>;
export type Insight = z.infer<typeof Insight>;
export type InsightsParams = z.infer<typeof InsightsParams>;
export type ListParams = z.infer<typeof ListParams>;
export type ListResponse<T> = { object: string; data: T[]; first_id?: string | null; last_id?: string | null; has_more: boolean; count?: number };

export class PagePromise<T> implements PromiseLike<ListResponse<T>> {
  constructor(private readonly fetchPage: (query: Record<string, unknown>) => Promise<ListResponse<T>>, private readonly initialQuery: Record<string, unknown>) {}
  then<TResult1 = ListResponse<T>, TResult2 = never>(onfulfilled?: ((value: ListResponse<T>) => TResult1 | PromiseLike<TResult1>) | null, onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | null): PromiseLike<TResult1 | TResult2> {
    return this.fetchPage(this.initialQuery).then(onfulfilled, onrejected);
  }
  async *[Symbol.asyncIterator](): AsyncGenerator<T> {
    let query = { ...this.initialQuery };
    for (;;) {
      const page = await this.fetchPage(query);
      yield* page.data;
      if (!page.has_more || !page.last_id) break;
      query = { ...query, after: page.last_id };
    }
  }
}

abstract class Resource {
  constructor(protected readonly client: APIClient) {}
  protected request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    return this.client.request<T>(method, path, options);
  }
  protected parse<T extends z.ZodTypeAny>(schema: T, value: unknown): z.infer<T> {
    try {
      return schema.parse(value);
    } catch (error) {
      throw new ValidationError("OpenAI Ads request failed validation", error);
    }
  }
}

const listResponse = <T extends z.ZodTypeAny>(item: T) => z.object({ object: z.string().default("list"), data: z.array(item), first_id: z.string().nullable().optional(), last_id: z.string().nullable().optional(), has_more: z.boolean(), count: z.number().optional() }).passthrough();

export class Campaigns extends Resource {
  list(params: ListParams = {}): PagePromise<Campaign> {
    const parsed = this.parse(ListParams, params);
    return new PagePromise((query) => this.request("GET", "/campaigns", { query, responseSchema: listResponse(Campaign) }), parsed);
  }
  create(params: CampaignCreateParams): Promise<Campaign> {
    return this.request("POST", "/campaigns", { body: this.parse(CampaignCreateParams, params), responseSchema: Campaign });
  }
  retrieve(id: string): Promise<Campaign> { return this.request("GET", `/campaigns/${encodeURIComponent(id)}`, { responseSchema: Campaign }); }
  update(id: string, params: CampaignUpdateParams): Promise<Campaign> { return this.request("POST", `/campaigns/${encodeURIComponent(id)}`, { body: this.parse(CampaignUpdateParams, params), responseSchema: Campaign }); }
  activate(id: string): Promise<Campaign> { return this.action(id, "activate"); }
  pause(id: string): Promise<Campaign> { return this.action(id, "pause"); }
  archive(id: string): Promise<Campaign> { return this.action(id, "archive"); }
  private action(id: string, action: string): Promise<Campaign> { return this.request("POST", `/campaigns/${encodeURIComponent(id)}/${action}`, { responseSchema: Campaign }); }
}

export class AdGroups extends Resource {
  list(params: ListParams & { campaignId: string }): PagePromise<AdGroup> {
    const { campaignId, ...rest } = params;
    const parsed = this.parse(ListParams, rest);
    return new PagePromise((query) => this.request("GET", "/ad_groups", { query: { campaign_id: campaignId, ...query }, responseSchema: listResponse(AdGroup) }), parsed);
  }
  create(params: AdGroupCreateParams): Promise<AdGroup> { return this.request("POST", "/ad_groups", { body: this.parse(AdGroupCreateParams, params), responseSchema: AdGroup }); }
  retrieve(id: string): Promise<AdGroup> { return this.request("GET", `/ad_groups/${encodeURIComponent(id)}`, { responseSchema: AdGroup }); }
  update(id: string, params: AdGroupUpdateParams): Promise<AdGroup> { return this.request("POST", `/ad_groups/${encodeURIComponent(id)}`, { body: this.parse(AdGroupUpdateParams, params), responseSchema: AdGroup }); }
  activate(id: string): Promise<AdGroup> { return this.action(id, "activate"); }
  pause(id: string): Promise<AdGroup> { return this.action(id, "pause"); }
  archive(id: string): Promise<AdGroup> { return this.action(id, "archive"); }
  private action(id: string, action: string): Promise<AdGroup> { return this.request("POST", `/ad_groups/${encodeURIComponent(id)}/${action}`, { responseSchema: AdGroup }); }
}

export class Ads extends Resource {
  list(params: ListParams & { adGroupId: string }): PagePromise<Ad> {
    const { adGroupId, ...rest } = params;
    const parsed = this.parse(ListParams, rest);
    return new PagePromise((query) => this.request("GET", "/ads", { query: { ad_group_id: adGroupId, ...query }, responseSchema: listResponse(Ad) }), parsed);
  }
  create(params: AdCreateParams): Promise<Ad> { return this.request("POST", "/ads", { body: this.parse(AdCreateParams, params), responseSchema: Ad }); }
  retrieve(id: string): Promise<Ad> { return this.request("GET", `/ads/${encodeURIComponent(id)}`, { responseSchema: Ad }); }
  update(id: string, params: AdUpdateParams): Promise<Ad> { return this.request("POST", `/ads/${encodeURIComponent(id)}`, { body: this.parse(AdUpdateParams, params), responseSchema: Ad }); }
  activate(id: string): Promise<Ad> { return this.action(id, "activate"); }
  pause(id: string): Promise<Ad> { return this.action(id, "pause"); }
  archive(id: string): Promise<Ad> { return this.action(id, "archive"); }
  private action(id: string, action: string): Promise<Ad> { return this.request("POST", `/ads/${encodeURIComponent(id)}/${action}`, { responseSchema: Ad }); }
}

export class Uploads extends Resource {
  create(params: z.infer<typeof UploadParams>): Promise<Upload> {
    const parsed = this.parse(UploadParams, params);
    if (parsed.file) {
      const formData = new FormData();
      formData.set("file", parsed.file);
      return this.request("POST", "/upload", { formData, responseSchema: Upload });
    }
    return this.request("POST", "/upload", { body: { image_url: parsed.image_url }, responseSchema: Upload });
  }
}

export class AdAccountResource extends Resource {
  retrieve(): Promise<AdAccount> { return this.request("GET", "/ad_account", { responseSchema: AdAccount }); }
}

export class Insights extends Resource {
  adAccount(params: InsightsParams = {}): PagePromise<Insight> { return this.list("/ad_account/insights", params); }
  campaign(id: string, params: InsightsParams = {}): PagePromise<Insight> { return this.list(`/campaigns/${encodeURIComponent(id)}/insights`, params); }
  adGroup(id: string, params: InsightsParams = {}): PagePromise<Insight> { return this.list(`/ad_groups/${encodeURIComponent(id)}/insights`, params); }
  ad(id: string, params: InsightsParams = {}): PagePromise<Insight> { return this.list(`/ads/${encodeURIComponent(id)}/insights`, params); }
  private list(path: string, params: InsightsParams): PagePromise<Insight> {
    const parsed = this.parse(InsightsParams, params);
    const query: Record<string, unknown> = { time_granularity: parsed.timeGranularity, aggregation_level: parsed.aggregationLevel, limit: parsed.limit, before: parsed.before, after: parsed.after, fields: parsed.fields, filters: parsed.filters, sort: parsed.sort };
    if (parsed.dateRange) query.time_ranges = [JSON.stringify({ type: "date_range", since: parsed.dateRange.since, until: parsed.dateRange.until })];
    return new PagePromise((pageQuery) => this.request("GET", path, { query: pageQuery, responseSchema: listResponse(Insight) }), compact(query));
  }
}

export class OpenAIAds {
  readonly campaigns: Campaigns;
  readonly adGroups: AdGroups;
  readonly ads: Ads;
  readonly uploads: Uploads;
  readonly adAccount: AdAccountResource;
  readonly insights: Insights;
  constructor(options: OpenAIAdsOptions = {}) {
    const client = new APIClient(options);
    this.campaigns = new Campaigns(client);
    this.adGroups = new AdGroups(client);
    this.ads = new Ads(client);
    this.uploads = new Uploads(client);
    this.adAccount = new AdAccountResource(client);
    this.insights = new Insights(client);
  }
}

export const schemas = { Campaign, CampaignCreateParams, CampaignUpdateParams, AdGroup, AdGroupCreateParams, AdGroupUpdateParams, Ad, AdCreateParams, AdUpdateParams, Upload, UploadParams, AdAccount, Insight, InsightsParams };

function appendQuery(url: URL, query?: Record<string, unknown>) {
  if (!query) return;
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) url.searchParams.append(`${key}[]`, String(item));
    } else {
      url.searchParams.set(key, String(value));
    }
  }
}
function compact(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).filter(([, v]) => v !== undefined && v !== null));
}
function sleep(ms: number) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function retryAfterMs(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const date = Date.parse(value);
  return Number.isFinite(date) ? Math.max(0, date - Date.now()) : undefined;
}
function toErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const candidate = body as { error?: { message?: unknown }; message?: unknown };
    if (typeof candidate.error?.message === "string") return candidate.error.message;
    if (typeof candidate.message === "string") return candidate.message;
  }
  return fallback;
}
function shouldRetry(status: number) { return status === 408 || status === 409 || status === 429 || status >= 500; }
function backoffMs(attempt: number) { return Math.min(1000 * 2 ** attempt, 8000) + Math.floor(Math.random() * 250); }
async function parseJSON(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return text; }
}
function toAPIError(response: Response, body: unknown): APIError {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  if (response.status === 401 || response.status === 403) return new AuthenticationError(response, body, requestId);
  if (response.status === 429) return new RateLimitError(response, body, requestId);
  return new APIError(toErrorMessage(body, `OpenAI Ads API request failed with status ${response.status}`), response.status, response, body, requestId);
}
function isAbort(error: unknown): boolean { return error instanceof DOMException && error.name === "AbortError"; }
function mergeSignals(primary: AbortSignal, secondary?: AbortSignal): AbortSignal {
  if (!secondary) return primary;
  const controller = new AbortController();
  const abort = () => controller.abort();
  primary.addEventListener("abort", abort, { once: true });
  secondary.addEventListener("abort", abort, { once: true });
  return controller.signal;
}
function isFutureDate(date: string): boolean {
  const parsed = Date.parse(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed)) return false;
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return parsed > todayUtc;
}
