import { Link } from "react-router-dom";
import type { Feature, FeatureKey } from "../config/features";
import { ArrowIcon, ChartIcon, ChatIcon, LayersIcon } from "./icons";

const ICONS: Record<FeatureKey, typeof ChartIcon> = { insights: ChartIcon, workflow: LayersIcon, questions: ChatIcon };

/** Accent colours live in CSS (.card--insights / .card--workflow / .card--questions). */
export default function FeatureCard({ feature }: { feature: Feature }) {
  const Icon = ICONS[feature.key];
  return (
    <Link to={feature.to} className={`card card--${feature.key}`}>
      <span className="card__icon"><Icon /></span>
      <span className="card__body">
        <span className="card__title">{feature.title}</span>
        <span className="card__text">{feature.description}</span>
      </span>
      <span className="card__go" aria-hidden="true"><ArrowIcon /></span>
    </Link>
  );
}
