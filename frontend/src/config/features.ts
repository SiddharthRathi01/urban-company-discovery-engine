// Static interface copy for the home screen. No analysis data lives here: all figures come from the API.
export type FeatureKey = "insights" | "workflow" | "questions";

export interface Feature {
  key: FeatureKey;
  title: string;
  description: string;
  to: string;
}

export const FEATURES: Feature[] = [
  { key: "insights", title: "Explore Insights", description: "Dive into customer feedback and key findings.", to: "/overview" },
  { key: "workflow", title: "See the Workflow", description: "Understand the end-to-end discovery process.", to: "/workflow" },
  { key: "questions", title: "Ask Questions", description: "Find evidence in customer feedback.", to: "/ask" },
];
