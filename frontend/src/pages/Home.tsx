import Backdrop from "../components/Backdrop";
import FeatureCard from "../components/FeatureCard";
import Header from "../components/Header";
import { FEATURES } from "../config/features";

export default function Home() {
  return (
    <div className="page">
      <Backdrop />
      <Header />
      <main className="hero">
        <p className="eyebrow"><span>Customer Discovery</span></p>
        <h1 className="hero__title">
          Turn Customer Feedback{" "}<br />
          into <span className="gradient-text">Product Insights</span>
        </h1>
        <p className="hero__lead">
          Explore real customer experiences, uncover key patterns and identify opportunities to drive repeat bookings.
        </p>
        <nav className="cards" aria-label="Main sections">
          {FEATURES.map((f) => <FeatureCard key={f.key} feature={f} />)}
        </nav>
      </main>
    </div>
  );
}
