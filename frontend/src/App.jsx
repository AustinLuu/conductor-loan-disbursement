import { useState } from "react";

function ApplicationListPlaceholder() {
  return <p>Application list goes here.</p>;
}

function ReviewQueuePlaceholder() {
  return <p>Review queue goes here.</p>;
}

const TABS = [
  { id: "applications", label: "Applications", Component: ApplicationListPlaceholder },
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
