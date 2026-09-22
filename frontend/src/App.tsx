import { BrowserRouter, Routes, Route } from "react-router-dom";
import TopNav from "./components/TopNav";
import Home from "./pages/Home";
import Search from "./pages/Search";
import Deals from "./pages/Deals";
import Insights from "./pages/Insights";
import HowItWorks from "./pages/HowItWorks";
import ListingDetail from "./pages/ListingDetail";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <TopNav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/deals" element={<Deals />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/listing/:id" element={<ListingDetail />} />
      </Routes>
      <footer className="footer">
        BikroyLens — an independent price benchmark, not affiliated with Bikroy.com.
      </footer>
    </BrowserRouter>
  );
}
