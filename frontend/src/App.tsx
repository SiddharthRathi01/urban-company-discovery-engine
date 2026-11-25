import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layout/AppShell";
import AnalysisPage from "./pages/AnalysisPage";
import AskPage from "./pages/AskPage";
import EvidencePage from "./pages/EvidencePage";
import FeedbackPage from "./pages/FeedbackPage";
import GoldenPage from "./pages/GoldenPage";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";
import ResultsPage from "./pages/ResultsPage";
import WorkflowPage from "./pages/WorkflowPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route element={<AppShell />}>
        <Route path="/overview" element={<Navigate to="/overview/feedback" replace />} />
        <Route path="/overview/feedback" element={<FeedbackPage />} />
        <Route path="/overview/analysis" element={<AnalysisPage />} />
        <Route path="/overview/evidence" element={<EvidencePage />} />
        <Route path="/overview/golden" element={<GoldenPage />} />
        <Route path="/results/:uploadId" element={<ResultsPage />} />
        <Route path="/workflow" element={<WorkflowPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
