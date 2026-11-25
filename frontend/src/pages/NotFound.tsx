import { Link } from "react-router-dom";
import { PageHero } from "../components/ui";

export default function NotFound() {
  return (
    <PageHero eyebrow="Not found" title={<span className="gradient-text">Page not found</span>} lede="This page does not exist.">
      <Link to="/" className="btn btn--primary">← Back to home</Link>
    </PageHero>
  );
}
