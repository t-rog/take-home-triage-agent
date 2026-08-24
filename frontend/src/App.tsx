import { NavLink, Route, Routes } from "react-router-dom";

import QueuePage from "./pages/QueuePage";
import SubmitPage from "./pages/SubmitPage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">Triage Agent</span>
        <nav>
          <NavLink to="/submit" className={({ isActive }) => (isActive ? "active" : "")}>
            Submit
          </NavLink>
          <NavLink to="/queue" className={({ isActive }) => (isActive ? "active" : "")}>
            Queue
          </NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<QueuePage />} />
          <Route path="/submit" element={<SubmitPage />} />
          <Route path="/queue" element={<QueuePage />} />
        </Routes>
      </main>
    </div>
  );
}
