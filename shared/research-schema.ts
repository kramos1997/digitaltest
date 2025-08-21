import { z } from "zod";

// Research Query Schema
export const researchQuerySchema = z.object({
  query: z.string().min(1, "Query cannot be empty"),
  language: z.string().default("en"),
  gdpr_mode: z.boolean().default(false),
});

export type ResearchQuery = z.infer<typeof researchQuerySchema>;

// Research Result Types - Updated to match Python API
export interface ResearchSource {
  title: string;
  url: string;
  relevance_score: number;
  key_findings: string;
  domain: string;
  last_updated?: string;
  content_length: number;
  quality_score: number;
}

export interface ResearchMetadata {
  sources_searched: number;
  sources_processed: number;
  research_time_seconds: number;
  confidence_score: number;
  query_type: string;
  sub_questions: string[];
}

export interface ResearchResult {
  query: string;
  answer: string;
  research_metadata: ResearchMetadata;
  sources: ResearchSource[];
  follow_up_suggestions: string[];
}

export interface ResearchStatus {
  status: "starting" | "expanding" | "searching" | "scraping" | "ranking" | "synthesizing" | "complete" | "error";
  message: string;
  progress?: number;
}