import SatelliteMap from "./components/SatelliteMap";
import SatellitePage from "./components/SatellitePage";
import { useHashRoute } from "./hooks/useHashRoute";

function App() {
  const route = useHashRoute();
  return route.page === "satellite" ? (
    <SatellitePage key={route.name} name={route.name} />
  ) : (
    <div>
      <SatelliteMap />
    </div>
  );
}

export default App;
