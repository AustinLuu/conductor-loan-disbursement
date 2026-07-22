import { useState } from "react";
import ApplicationList from "./components/ApplicationList.jsx";
import ReviewQueuePlaceholder from "./components/ReviewQueuePlaceholder.jsx";

const TABS = [
  { id: "applications", label: "Applications", Component: ApplicationList },
  { id: "reviews", label: "Review Queue", Component: ReviewQueuePlaceholder },
];

export default function App() {
  const [activeTab, setActiveTab] = useState(TABS[0].id);
  const ActiveComponent = TABS.find((t) => t.id === activeTab).Component;

  return (
    <>
      <header className="app-header">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={tab.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </header>
      <main>
        <ActiveComponent />
      </main>
    </>
  );
}
