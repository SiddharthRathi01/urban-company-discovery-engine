import { Link } from "react-router-dom";

/** Text-only brand lockup. The Urban Company logo is intentionally not used. */
export default function Header() {
  return (
    <header className="header">
      <Link to="/" className="header__brand" aria-label="Urban Company Discovery Engine, home">
        <span className="header__company">Urban Company</span>
        <span className="header__divider" aria-hidden="true" />
        <span className="header__product">Discovery Engine</span>
      </Link>
    </header>
  );
}
