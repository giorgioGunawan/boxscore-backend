const axios = require('axios');

const BASE_URL = 'https://f1apibackend-1.onrender.com/api';
// const BASE_URL = 'http://localhost:3000/api';

// Helper function to make API requests
async function makeRequest(method, endpoint, data = null) {
  try {
    const url = `${BASE_URL}${endpoint}`;
    const response = await axios({
      method,
      url,
      data,
    });
    console.log(`${method} ${endpoint} - Success:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`${method} ${endpoint} - Error:`, error.response?.data || error.message);
    return null;
  }
}

// Add driver standings for 2024 season
async function addDriverStandings() {
  const drivers = [
    { driver_name: "Max Verstappen", team_name: "Red Bull Racing", points: 195, driver_number: 1 },
    { driver_name: "Sergio Perez", team_name: "Red Bull Racing", points: 127, driver_number: 11 },
    { driver_name: "Charles Leclerc", team_name: "Ferrari", points: 150, driver_number: 16 },
    { driver_name: "Carlos Sainz", team_name: "Ferrari", points: 146, driver_number: 55 },
    { driver_name: "Lando Norris", team_name: "McLaren", points: 138, driver_number: 4 },
    { driver_name: "Oscar Piastri", team_name: "McLaren", points: 91, driver_number: 81 },
    { driver_name: "George Russell", team_name: "Mercedes", points: 85, driver_number: 63 },
    { driver_name: "Lewis Hamilton", team_name: "Mercedes", points: 85, driver_number: 44 },
    { driver_name: "Fernando Alonso", team_name: "Aston Martin", points: 41, driver_number: 14 },
    { driver_name: "Lance Stroll", team_name: "Aston Martin", points: 17, driver_number: 18 },
    { driver_name: "Yuki Tsunoda", team_name: "RB", points: 19, driver_number: 22 },
    { driver_name: "Daniel Ricciardo", team_name: "RB", points: 9, driver_number: 3 },
    { driver_name: "Nico Hulkenberg", team_name: "Haas F1 Team", points: 9, driver_number: 27 },
    { driver_name: "Kevin Magnussen", team_name: "Haas F1 Team", points: 5, driver_number: 20 },
    { driver_name: "Alexander Albon", team_name: "Williams", points: 4, driver_number: 23 },
    { driver_name: "Logan Sargeant", team_name: "Williams", points: 0, driver_number: 2 },
    { driver_name: "Esteban Ocon", team_name: "Alpine", points: 1, driver_number: 31 },
    { driver_name: "Pierre Gasly", team_name: "Alpine", points: 1, driver_number: 10 },
    { driver_name: "Valtteri Bottas", team_name: "Kick Sauber", points: 0, driver_number: 77 },
    { driver_name: "Zhou Guanyu", team_name: "Kick Sauber", points: 0, driver_number: 24 }
  ];

  for (const driver of drivers) {
    await makeRequest('POST', '/driver-standings', driver);
  }
  console.log('All driver standings added successfully');
}

// Add constructor standings for 2024 season
async function addConstructorStandings() {
  const constructors = [
    { constructor_name: "Red Bull Racing", points: 322, driver_name_1: "Max Verstappen", driver_name_2: "Sergio Perez" },
    { constructor_name: "Ferrari", points: 296, driver_name_1: "Charles Leclerc", driver_name_2: "Carlos Sainz" },
    { constructor_name: "McLaren", points: 229, driver_name_1: "Lando Norris", driver_name_2: "Oscar Piastri" },
    { constructor_name: "Mercedes", points: 170, driver_name_1: "Lewis Hamilton", driver_name_2: "George Russell" },
    { constructor_name: "Aston Martin", points: 58, driver_name_1: "Fernando Alonso", driver_name_2: "Lance Stroll" },
    { constructor_name: "RB", points: 28, driver_name_1: "Yuki Tsunoda", driver_name_2: "Daniel Ricciardo" },
    { constructor_name: "Haas F1 Team", points: 14, driver_name_1: "Nico Hulkenberg", driver_name_2: "Kevin Magnussen" },
    { constructor_name: "Williams", points: 4, driver_name_1: "Alexander Albon", driver_name_2: "Logan Sargeant" },
    { constructor_name: "Alpine", points: 2, driver_name_1: "Esteban Ocon", driver_name_2: "Pierre Gasly" },
    { constructor_name: "Kick Sauber", points: 0, driver_name_1: "Valtteri Bottas", driver_name_2: "Zhou Guanyu" }
  ];

  for (const constructor of constructors) {
    await makeRequest('POST', '/constructor-standings', constructor);
  }
  console.log('All constructor standings added successfully');
}

// Add races for 2024 season
async function addRaces() {
  const races = [
    {
      round: 1,
      name: "Bahrain Grand Prix",
      location: "Bahrain International Circuit",
      datetime_fp1: 1709211600, // March 1, 2024
      datetime_fp2: 1709226000,
      datetime_fp3: 1709298000,
      datetime_qualifying: 1709312400,
      datetime_race: 1709398800, // March 2, 2024
      first_place: "Max Verstappen",
      second_place: "Sergio Perez",
      third_place: "Carlos Sainz"
    },
    {
      round: 2,
      name: "Saudi Arabian Grand Prix",
      location: "Jeddah Corniche Circuit",
      datetime_fp1: 1709816400, // March 7, 2024
      datetime_fp2: 1709830800,
      datetime_fp3: 1709902800,
      datetime_qualifying: 1709917200,
      datetime_race: 1710003600, // March 9, 2024
      first_place: "Max Verstappen",
      second_place: "Charles Leclerc",
      third_place: "Sergio Perez"
    },
    {
      round: 3,
      name: "Australian Grand Prix",
      location: "Albert Park Circuit",
      datetime_fp1: 1711026000, // March 22, 2024
      datetime_fp2: 1711040400,
      datetime_fp3: 1711112400,
      datetime_qualifying: 1711126800,
      datetime_race: 1711213200, // March 24, 2024
      first_place: "Carlos Sainz",
      second_place: "Charles Leclerc",
      third_place: "Lando Norris"
    },
    {
      round: 4,
      name: "Japanese Grand Prix",
      location: "Suzuka Circuit",
      datetime_fp1: 1712235600, // April 5, 2024
      datetime_fp2: 1712250000,
      datetime_fp3: 1712322000,
      datetime_qualifying: 1712336400,
      datetime_race: 1712422800, // April 7, 2024
      first_place: "Max Verstappen",
      second_place: "Sergio Perez",
      third_place: "Carlos Sainz"
    },
    {
      round: 5,
      name: "Chinese Grand Prix",
      location: "Shanghai International Circuit",
      datetime_fp1: 1713445200, // April 19, 2024
      datetime_fp2: 1713459600,
      datetime_sprint: 1713531600,
      datetime_qualifying: 1713546000,
      datetime_race: 1713632400, // April 21, 2024
      first_place: "Max Verstappen",
      second_place: "Lando Norris",
      third_place: "Sergio Perez"
    },
    {
      round: 6,
      name: "Miami Grand Prix",
      location: "Miami International Autodrome",
      datetime_fp1: 1714654800, // May 3, 2024
      datetime_fp2: 1714669200,
      datetime_sprint: 1714741200,
      datetime_qualifying: 1714755600,
      datetime_race: 1714842000, // May 5, 2024
      first_place: "Lando Norris",
      second_place: "Max Verstappen",
      third_place: "Charles Leclerc"
    },
    {
      round: 7,
      name: "Emilia Romagna Grand Prix",
      location: "Autodromo Enzo e Dino Ferrari",
      datetime_fp1: 1716469200, // May 17, 2024
      datetime_fp2: 1716483600,
      datetime_fp3: 1716555600,
      datetime_qualifying: 1716570000,
      datetime_race: 1716656400, // May 19, 2024
      first_place: "Max Verstappen",
      second_place: "Lando Norris",
      third_place: "Charles Leclerc"
    },
    {
      round: 8,
      name: "Monaco Grand Prix",
      location: "Circuit de Monaco",
      datetime_fp1: 1717074000, // May 24, 2024
      datetime_fp2: 1717088400,
      datetime_fp3: 1717160400,
      datetime_qualifying: 1717174800,
      datetime_race: 1717261200, // May 26, 2024
      first_place: "Charles Leclerc",
      second_place: "Oscar Piastri",
      third_place: "Carlos Sainz"
    },
    // Add upcoming races with null podium results
    {
      round: 9,
      name: "Canadian Grand Prix",
      location: "Circuit Gilles Villeneuve",
      datetime_fp1: 1718283600, // June 7, 2024
      datetime_fp2: 1718298000,
      datetime_fp3: 1718370000,
      datetime_qualifying: 1718384400,
      datetime_race: 1718470800, // June 9, 2024
      first_place: null,
      second_place: null,
      third_place: null
    },
    {
      round: 10,
      name: "Spanish Grand Prix",
      location: "Circuit de Barcelona-Catalunya",
      datetime_fp1: 1719493200, // June 21, 2024
      datetime_fp2: 1719507600,
      datetime_fp3: 1719579600,
      datetime_qualifying: 1719594000,
      datetime_race: 1719680400, // June 23, 2024
      first_place: null,
      second_place: null,
      third_place: null
    }
  ];

  for (const race of races) {
    await makeRequest('POST', '/races', race);
  }
  console.log('All races added successfully');
}

// Add race results for completed races
async function addRaceResults() {
  // We'll add results for the first race (Bahrain GP) as an example
  const bahrainResults = [
    {
      race_id: 1,
      session_type: "race",
      position: 1,
      driver_name: "Max Verstappen",
      team_name: "Red Bull Racing",
      time: "1:31:44.742",
      laps: 57,
      points: 25
    },
    {
      race_id: 1,
      session_type: "race",
      position: 2,
      driver_name: "Sergio Perez",
      team_name: "Red Bull Racing",
      time: "+22.457s",
      laps: 57,
      points: 18
    },
    {
      race_id: 1,
      session_type: "race",
      position: 3,
      driver_name: "Carlos Sainz",
      team_name: "Ferrari",
      time: "+25.110s",
      laps: 57,
      points: 15
    },
    {
      race_id: 1,
      session_type: "race",
      position: 4,
      driver_name: "Charles Leclerc",
      team_name: "Ferrari",
      time: "+45.208s",
      laps: 57,
      points: 12
    },
    {
      race_id: 1,
      session_type: "race",
      position: 5,
      driver_name: "George Russell",
      team_name: "Mercedes",
      time: "+46.128s",
      laps: 57,
      points: 10
    },
    {
      race_id: 1,
      session_type: "qualifying",
      position: 1,
      driver_name: "Max Verstappen",
      team_name: "Red Bull Racing",
      time: "1:29.179",
      laps: 18,
      points: 0
    },
    {
      race_id: 1,
      session_type: "qualifying",
      position: 2,
      driver_name: "Charles Leclerc",
      team_name: "Ferrari",
      time: "1:29.407",
      laps: 18,
      points: 0
    }
  ];

  for (const result of bahrainResults) {
    await makeRequest('POST', '/results', result);
  }
  console.log('Race results added successfully');
}

// Add example live race data
async function addLiveRaceExample() {
  // First clear any existing live race data
  await makeRequest('DELETE', '/live-race');
  
  const liveRaceData = [
    {
      driver_name: "Max Verstappen",
      team_name: "Red Bull Racing",
      car_number: 1,
      position: 1,
      time_behind: "LEADER",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Lando Norris",
      team_name: "McLaren",
      car_number: 4,
      position: 2,
      time_behind: "+3.254s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Charles Leclerc",
      team_name: "Ferrari",
      car_number: 16,
      position: 3,
      time_behind: "+5.127s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Sergio Perez",
      team_name: "Red Bull Racing",
      car_number: 11,
      position: 4,
      time_behind: "+8.932s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Carlos Sainz",
      team_name: "Ferrari",
      car_number: 55,
      position: 5,
      time_behind: "+12.541s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Lewis Hamilton",
      team_name: "Mercedes",
      car_number: 44,
      position: 6,
      time_behind: "+15.876s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "George Russell",
      team_name: "Mercedes",
      car_number: 63,
      position: 7,
      time_behind: "+18.234s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Fernando Alonso",
      team_name: "Aston Martin",
      car_number: 14,
      position: 8,
      time_behind: "+25.123s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Oscar Piastri",
      team_name: "McLaren",
      car_number: 81,
      position: 9,
      time_behind: "+27.654s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Lance Stroll",
      team_name: "Aston Martin",
      car_number: 18,
      position: 10,
      time_behind: "+35.789s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Daniel Ricciardo",
      team_name: "RB",
      car_number: 3,
      position: 11,
      time_behind: "+42.345s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Yuki Tsunoda",
      team_name: "RB",
      car_number: 22,
      position: 12,
      time_behind: "+48.912s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Nico Hulkenberg",
      team_name: "Haas F1 Team",
      car_number: 27,
      position: 13,
      time_behind: "+55.432s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Alexander Albon",
      team_name: "Williams",
      car_number: 23,
      position: 14,
      time_behind: "+62.123s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Kevin Magnussen",
      team_name: "Haas F1 Team",
      car_number: 20,
      position: 15,
      time_behind: "+68.765s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Esteban Ocon",
      team_name: "Alpine",
      car_number: 31,
      position: 16,
      time_behind: "+75.432s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Pierre Gasly",
      team_name: "Alpine",
      car_number: 10,
      position: 17,
      time_behind: "+82.109s",
      current_lap: 45,
      is_dnf: 0
    },
    {
      driver_name: "Valtteri Bottas",
      team_name: "Kick Sauber",
      car_number: 77,
      position: 18,
      time_behind: "+1 LAP",
      current_lap: 44,
      is_dnf: 0
    },
    {
      driver_name: "Zhou Guanyu",
      team_name: "Kick Sauber",
      car_number: 24,
      position: 19,
      time_behind: "+1 LAP",
      current_lap: 44,
      is_dnf: 0
    },
    {
      driver_name: "Logan Sargeant",
      team_name: "Williams",
      car_number: 2,
      position: 20,
      time_behind: "DNF",
      current_lap: 32,
      is_dnf: 1
    }
  ];

  for (const entry of liveRaceData) {
    await makeRequest('POST', '/live-race', entry);
  }
  console.log('Live race example data added successfully');
}

// Main function to run all data loading
async function loadAllData() {
  console.log('Starting F1 data loading...');
  
  await addDriverStandings();
  await addConstructorStandings();
  await addRaces();
  await addRaceResults();
  await addLiveRaceExample();
  
  console.log('All F1 data loaded successfully!');
}

// Run the data loader
loadAllData().catch(error => {
  console.error('Error loading data:', error);
}); 