import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Search from "./pages/Search";
import Companies from "./pages/Companies";
import CompanyView from "./pages/CompanyView";
import CrawlHistory from "./pages/CrawlHistory";
import Pipeline from "./pages/Pipeline";
import TradeAnalytics from "./pages/TradeAnalytics";
import Exports from "./pages/Exports";
import Settings from "./pages/Settings";

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/search" element={<Search />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/company/:id" element={<CompanyView />} />
        <Route path="/crawls" element={<CrawlHistory />} />
        <Route path="/crm/pipeline" element={<Pipeline />} />
        <Route path="/analytics" element={<TradeAnalytics />} />
        <Route path="/exports" element={<Exports />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

export default App;
