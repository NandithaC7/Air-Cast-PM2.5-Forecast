import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AppDataProvider } from "./context/AppData";
import { DashboardPage } from "./pages/DashboardPage";
import { DataExplorerPage } from "./pages/DataExplorerPage";
import { ForecastPage } from "./pages/ForecastPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { ModelComparisonPage } from "./pages/ModelComparisonPage";

export default function App() {
  return (
    <BrowserRouter>
      <AppDataProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/data" element={<DataExplorerPage />} />
            <Route path="/models" element={<ModelComparisonPage />} />
            <Route path="/forecast" element={<ForecastPage />} />
            <Route path="/methodology" element={<MethodologyPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AppDataProvider>
    </BrowserRouter>
  );
}
