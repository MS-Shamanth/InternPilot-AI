/**
 * TypeScript mirrors of the backend API contract (design.md §8, §8.3; backend/app/schemas/*).
 *
 * Field names are the backend's snake_case JSON names, unchanged. Nullable fields are always
 * present (`T | null`). Dates are `YYYY-MM-DD` strings and timestamps ISO-8601 UTC with `Z`.
 */

/** A calendar date, `YYYY-MM-DD`. */
export type IsoDate = string;
/** A timestamp, ISO-8601 UTC with a `Z` suffix. */
export type IsoDateTime = string;

export type JsonValue =
  string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = Record<string, JsonValue>;

// ---------- Enums (string values, exact casing) ----------

export type ApplicationStatus =
  | 'Saved'
  | 'Interested'
  | 'Applied'
  | 'Assessment'
  | 'Interview'
  | 'Rejected'
  | 'Offer'
  | 'Withdrawn';
export type WorkMode = 'remote' | 'hybrid' | 'onsite';
export type EmploymentType = 'internship' | 'full_time' | 'part_time' | 'contract';
export type ExperienceLevel = 'internship' | 'entry' | 'junior' | 'mid' | 'senior';
export type EducationLevel = 'high_school' | 'diploma' | 'bachelor' | 'master' | 'phd';
export type JobSource = 'seed' | 'fixture' | 'remotive' | 'arbeitnow' | 'payload';
export type SalaryPeriod = 'year' | 'month' | 'hour';
export type JobSortKey =
  'match_score' | 'discovered_at' | 'deadline' | 'title' | 'company' | 'salary';
export type SortOrder = 'asc' | 'desc';

// ---------- Common ----------

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  /** 0 when `total` is 0. */
  total_pages: number;
}

/** One entry of a 422 `VALIDATION_ERROR` envelope's `details` list. */
export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** `details` of the error envelope: a validation list, a structured object, or `null`. */
export type ApiErrorDetails = ValidationErrorItem[] | Record<string, unknown> | null;

/** The error envelope every failing endpoint (except `/health`) returns (design.md §8.2). */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: ApiErrorDetails;
  };
}

// ---------- Profile ----------

export interface EducationEntry {
  institution: string;
  degree: string | null;
  field: string | null;
  start_year: number | null;
  end_year: number | null;
}

export interface Project {
  name: string;
  description: string;
  technologies: string[];
  url: string | null;
}

export interface Certification {
  name: string;
  issuer: string | null;
  year: number | null;
}

export interface Profile {
  id: number;
  name: string;
  email: string;
  location: string | null;
  target_roles: string[];
  preferred_locations: string[];
  preferred_work_modes: WorkMode[];
  experience_level: ExperienceLevel | null;
  education_level: EducationLevel | null;
  education: EducationEntry[];
  /** Display names, sorted by normalized name. */
  technical_skills: string[];
  soft_skills: string[];
  projects: Project[];
  certifications: Certification[];
  resume_text: string;
  github_url: string | null;
  portfolio_url: string | null;
  linkedin_url: string | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** `PUT /profile` body: a full replace, so every field is sent. */
export type ProfileUpdate = Omit<Profile, 'id' | 'created_at' | 'updated_at'>;

// ---------- Matching ----------

export type FactorKey =
  | 'required_skills'
  | 'preferred_skills'
  | 'role_similarity'
  | 'experience'
  | 'location'
  | 'work_mode'
  | 'education'
  | 'projects';

export interface Factor {
  key: FactorKey;
  label: string;
  weight: number;
  /** Rounded to 2 decimals. */
  points: number;
  /** Rounded to 4 decimals. */
  ratio: number;
  detail: string;
}

export interface MatchExplanation {
  job_id: number;
  score: number;
  algorithm_version: string;
  /** All eight factors in engine order. */
  factors: Factor[];
  matched_required_skills: string[];
  missing_required_skills: string[];
  matched_preferred_skills: string[];
  missing_preferred_skills: string[];
  positive_reasons: string[];
  negative_reasons: string[];
}

// ---------- Applications ----------

export interface ApplicationJob {
  id: number;
  title: string;
  company: string;
  location: string;
  deadline: IsoDate | null;
}

export interface Application {
  id: number;
  job_id: number;
  status: ApplicationStatus;
  applied_at: IsoDate | null;
  deadline: IsoDate | null;
  interview_date: IsoDateTime | null;
  recruiter_name: string | null;
  recruiter_email: string | null;
  notes: string;
  outcome: string | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  job: ApplicationJob;
}

/** `POST /applications`; omitted fields take the backend defaults (status `Saved`). */
export interface ApplicationCreate {
  job_id: number;
  status?: ApplicationStatus;
  notes?: string;
  applied_at?: IsoDate | null;
  deadline?: IsoDate | null;
  interview_date?: IsoDateTime | null;
  recruiter_name?: string | null;
  recruiter_email?: string | null;
  outcome?: string | null;
}

/**
 * `PATCH /applications/{id}`: only present fields are applied; `null` clears a nullable field.
 * `status` and `notes` are not nullable.
 */
export interface ApplicationUpdate {
  status?: ApplicationStatus;
  notes?: string;
  applied_at?: IsoDate | null;
  deadline?: IsoDate | null;
  interview_date?: IsoDateTime | null;
  recruiter_name?: string | null;
  recruiter_email?: string | null;
  outcome?: string | null;
}

export interface ApplicationsMeta {
  /** Canonical order. */
  statuses: ApplicationStatus[];
  /** Allowed targets per status, in canonical order. */
  transitions: Record<ApplicationStatus, ApplicationStatus[]>;
}

export interface ApplicationListParams {
  /** Sent as repeated `status` parameters. */
  status?: ApplicationStatus[];
}

// ---------- Jobs ----------

export interface JobState {
  job_id: number;
  is_bookmarked: boolean;
  is_hidden: boolean;
}

export interface JobSummary {
  id: number;
  title: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  experience_level: ExperienceLevel | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: SalaryPeriod | null;
  deadline: IsoDate | null;
  source: JobSource;
  discovered_at: IsoDateTime;
  /** Display names, sorted by normalized name. */
  required_skills: string[];
  preferred_skills: string[];
  /** 0–100 from the matching engine (design.md §8.3). */
  match_score: number;
  is_bookmarked: boolean;
  is_hidden: boolean;
  application_status: ApplicationStatus | null;
}

export interface JobDetail extends JobSummary {
  description: string;
  application_url: string;
  min_education_level: EducationLevel | null;
  /** Design.md §8.3. */
  match_explanation: MatchExplanation;
  application: Application | null;
}

/** Query of `GET /jobs`; omitted values use the backend defaults (sort `match_score`, page 1, 20). */
export interface JobListParams {
  q?: string;
  /** Repeated parameters, any-of. */
  employment_type?: EmploymentType[];
  work_mode?: WorkMode[];
  experience_level?: ExperienceLevel[];
  location?: string;
  source?: JobSource;
  /** Sent comma-separated; at most 10 distinct skills. */
  skills?: string[];
  /** 0–100. */
  min_score?: number;
  bookmarked?: boolean;
  include_hidden?: boolean;
  sort?: JobSortKey;
  order?: SortOrder;
  page?: number;
  /** 1–100. */
  page_size?: number;
}

// ---------- Recommendations ----------

export interface Recommendation {
  job: JobSummary;
  match_explanation: MatchExplanation;
}

// ---------- Dashboard ----------

export type DeadlineKind = 'application' | 'bookmark';

export interface UpcomingDeadline {
  job_id: number;
  application_id: number | null;
  title: string;
  company: string;
  deadline: IsoDate;
  days_left: number;
  kind: DeadlineKind;
}

export type ActivityType =
  | 'application_created'
  | 'status_changed'
  | 'application_updated'
  | 'application_deleted'
  | 'job_bookmarked'
  | 'job_hidden'
  | 'profile_updated'
  | 'jobs_ingested';

export interface ActivityItem {
  id: number;
  type: ActivityType;
  message: string;
  job_id: number | null;
  application_id: number | null;
  created_at: IsoDateTime;
}

export interface TopRecommendation {
  job_id: number;
  title: string;
  company: string;
  location: string;
  score: number;
}

export interface StatusCount {
  status: ApplicationStatus;
  count: number;
}

export interface WeeklyApplicationCount {
  /** Monday of the ISO week. */
  week_start: IsoDate;
  count: number;
}

export type ScoreBucket = '0-19' | '20-39' | '40-59' | '60-79' | '80-100';

export interface ScoreBucketCount {
  bucket: ScoreBucket;
  count: number;
}

export interface Dashboard {
  total_jobs_discovered: number;
  matching_jobs: number;
  applications_submitted: number;
  interviews_scheduled: number;
  offers_received: number;
  /** Percentage, 1 decimal. */
  response_rate: number;
  upcoming_deadlines: UpcomingDeadline[];
  recent_activity: ActivityItem[];
  top_recommendations: TopRecommendation[];
  status_breakdown: StatusCount[];
  applications_over_time: WeeklyApplicationCount[];
  score_distribution: ScoreBucketCount[];
}

// ---------- Resume analysis ----------

export interface ResumeAnalyzeRequest {
  job_id: number;
  /** Omitted, null or blank → the profile's resume text is used. */
  resume_text?: string | null;
}

export type ResumeSource = 'request' | 'profile';

export interface ResumeMatchingSkill {
  skill: string;
  is_required: boolean;
}

export interface ResumeMissingSkill {
  skill: string;
  is_required: boolean;
  in_profile: boolean;
}

export interface ResumeRelevantProject {
  name: string;
  matched_skills: string[];
  mentioned_in_resume: boolean;
}

export type ResumeSuggestionRule =
  | 'ADD_PROFILE_SKILL'
  | 'GAP_REQUIRED_SKILL'
  | 'MENTION_PROJECT'
  | 'ADD_KEYWORDS'
  | 'QUANTIFY'
  | 'LENGTH_SHORT'
  | 'LENGTH_LONG'
  | 'ADD_LINKS';

export interface ResumeSuggestion {
  rule: ResumeSuggestionRule;
  message: string;
  evidence: string[];
}

export interface ResumeAnalysis {
  job_id: number;
  resume_source: ResumeSource;
  word_count: number;
  compatibility_score: number;
  matching_skills: ResumeMatchingSkill[];
  missing_skills: ResumeMissingSkill[];
  relevant_projects: ResumeRelevantProject[];
  missing_keywords: string[];
  suggestions: ResumeSuggestion[];
  match_explanation: MatchExplanation;
}

// ---------- Interview prep ----------

export type InterviewProviderName = 'template' | 'llm';
export type InterviewCategory = 'role' | 'technical' | 'skill' | 'project' | 'hr';
export type PrepPriority = 'high' | 'medium' | 'low';

export interface InterviewQuestion {
  /** `"{category}-{n}"`. */
  id: string;
  category: InterviewCategory;
  text: string;
  skill: string | null;
}

export interface InterviewSection {
  category: InterviewCategory;
  title: string;
  questions: InterviewQuestion[];
}

export interface PrepTopic {
  topic: string;
  reason: string;
  priority: PrepPriority;
}

export interface InterviewPrep {
  job_id: number;
  provider: InterviewProviderName;
  sections: InterviewSection[];
  prep_topics: PrepTopic[];
}

// ---------- Ingestion ----------

export type IngestSourceName = 'fixture' | 'remotive' | 'arbeitnow' | 'payload';
export type RawFormat = 'remotive' | 'arbeitnow' | 'normalized';

interface IngestRequestBase {
  /** Default `true`: public-source failures fall back to fixtures. */
  fallback?: boolean;
  /** 1–500, default 100. */
  limit?: number;
}

export interface IngestSourceRequest extends IngestRequestBase {
  source: Exclude<IngestSourceName, 'payload'>;
}

/** A captured payload (e.g. from the MCP fetch server); at most 500 items. */
export interface IngestPayloadRequest extends IngestRequestBase {
  source: 'payload';
  format: RawFormat;
  /** A list of items, or an object with a `jobs` or `data` list. */
  payload: JsonObject | JsonValue[];
}

export type IngestRequest = IngestSourceRequest | IngestPayloadRequest;

export interface IngestError {
  /** Item index for a rejected item; `null` for a source failure. */
  index: number | null;
  reason: string;
}

export interface IngestResult {
  requested_source: IngestSourceName;
  source: IngestSourceName;
  fallback_used: boolean;
  fetched: number;
  created: number;
  updated: number;
  duplicates: number;
  rejected: number;
  /** At most 50 entries. */
  errors: IngestError[];
}

// ---------- Health ----------

export interface HealthResponse {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unavailable';
  version: string;
}
