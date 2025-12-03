import fetch from 'node-fetch';


// Function to convert UTC time to Unix timestamp
function convertToTimestamp(utcTimeStr) {
  if (!utcTimeStr || utcTimeStr === "-") return null;
  
  // Parse the date and time (format: 2025-03-14 01:30)
  const [dateStr, timeStr] = utcTimeStr.split(' ');
  const [year, month, day] = dateStr.split('-').map(num => parseInt(num));
  const [hours, minutes] = timeStr.split(':').map(num => parseInt(num));
  
  // Create date object in UTC
  const date = new Date(Date.UTC(year, month - 1, day, hours, minutes, 0, 0));
  
  // Return Unix timestamp (seconds since epoch)
  return Math.floor(date.getTime() / 1000);
}

// Race data for the 2025 F1 season with correct dates and times in UTC
const races = [
  {
    "round": "1",
    "name": "Australian Grand Prix",
    "location": "Albert Park Circuit, Melbourne",
    "datetime_fp1": convertToTimestamp("2025-03-14 01:30"),
    "datetime_fp2": convertToTimestamp("2025-03-14 05:00"),
    "datetime_fp3": convertToTimestamp("2025-03-15 01:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-03-15 05:00"),
    "datetime_race": convertToTimestamp("2025-03-16 04:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "2",
    "name": "Chinese Grand Prix",
    "location": "Shanghai International Circuit, Shanghai",
    "datetime_fp1": convertToTimestamp("2025-03-21 03:30"),
    "datetime_fp2": convertToTimestamp("2025-03-21 07:30"),
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-03-22 03:00"),
    "datetime_qualifying": convertToTimestamp("2025-03-22 07:00"),
    "datetime_race": convertToTimestamp("2025-03-23 07:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "3",
    "name": "Japanese Grand Prix",
    "location": "Suzuka International Racing Course",
    "datetime_fp1": convertToTimestamp("2025-04-04 02:30"),
    "datetime_fp2": convertToTimestamp("2025-04-04 06:00"),
    "datetime_fp3": convertToTimestamp("2025-04-05 02:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-04-05 06:00"),
    "datetime_race": convertToTimestamp("2025-04-06 05:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "4",
    "name": "Bahrain Grand Prix",
    "location": "Bahrain International Circuit, Sakhir",
    "datetime_fp1": convertToTimestamp("2025-04-11 11:30"),
    "datetime_fp2": convertToTimestamp("2025-04-11 15:00"),
    "datetime_fp3": convertToTimestamp("2025-04-12 12:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-04-12 16:00"),
    "datetime_race": convertToTimestamp("2025-04-13 15:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "5",
    "name": "Saudi Arabian Grand Prix",
    "location": "Jeddah Corniche Circuit, Jeddah",
    "datetime_fp1": convertToTimestamp("2025-04-18 13:30"),
    "datetime_fp2": convertToTimestamp("2025-04-18 17:00"),
    "datetime_fp3": convertToTimestamp("2025-04-19 13:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-04-19 17:00"),
    "datetime_race": convertToTimestamp("2025-04-20 17:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "6",
    "name": "Miami Grand Prix",
    "location": "Miami International Autodrome, Miami",
    "datetime_fp1": convertToTimestamp("2025-05-02 16:30"),
    "datetime_fp2": null,
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-05-03 16:00"),
    "datetime_qualifying": convertToTimestamp("2025-05-03 20:00"),
    "datetime_race": convertToTimestamp("2025-05-04 20:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "7",
    "name": "Emilia Romagna Grand Prix",
    "location": "Imola Circuit, Imola",
    "datetime_fp1": convertToTimestamp("2025-05-16 11:30"),
    "datetime_fp2": convertToTimestamp("2025-05-16 15:00"),
    "datetime_fp3": convertToTimestamp("2025-05-17 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-05-17 14:00"),
    "datetime_race": convertToTimestamp("2025-05-18 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "8",
    "name": "Monaco Grand Prix",
    "location": "Circuit de Monaco, Monte Carlo",
    "datetime_fp1": convertToTimestamp("2025-05-23 11:30"),
    "datetime_fp2": convertToTimestamp("2025-05-23 15:00"),
    "datetime_fp3": convertToTimestamp("2025-05-24 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-05-24 14:00"),
    "datetime_race": convertToTimestamp("2025-05-25 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "9",
    "name": "Spanish Grand Prix",
    "location": "Circuit de Barcelona-Catalunya, Montmeló",
    "datetime_fp1": convertToTimestamp("2025-05-30 11:30"),
    "datetime_fp2": convertToTimestamp("2025-05-30 15:00"),
    "datetime_fp3": convertToTimestamp("2025-05-31 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-05-31 14:00"),
    "datetime_race": convertToTimestamp("2025-06-01 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "10",
    "name": "Canadian Grand Prix",
    "location": "Circuit Gilles Villeneuve, Montreal",
    "datetime_fp1": convertToTimestamp("2025-06-13 17:30"),
    "datetime_fp2": convertToTimestamp("2025-06-13 21:00"),
    "datetime_fp3": convertToTimestamp("2025-06-14 16:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-06-14 20:00"),
    "datetime_race": convertToTimestamp("2025-06-15 18:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "11",
    "name": "Austrian Grand Prix",
    "location": "Red Bull Ring, Spielberg",
    "datetime_fp1": convertToTimestamp("2025-06-27 11:30"),
    "datetime_fp2": convertToTimestamp("2025-06-27 15:00"),
    "datetime_fp3": convertToTimestamp("2025-06-28 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-06-28 14:00"),
    "datetime_race": convertToTimestamp("2025-06-29 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "12",
    "name": "British Grand Prix",
    "location": "Silverstone Circuit, Silverstone",
    "datetime_fp1": convertToTimestamp("2025-07-04 11:30"),
    "datetime_fp2": convertToTimestamp("2025-07-04 15:00"),
    "datetime_fp3": convertToTimestamp("2025-07-05 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-07-05 14:00"),
    "datetime_race": convertToTimestamp("2025-07-06 14:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "13",
    "name": "Belgian Grand Prix",
    "location": "Circuit de Spa-Francorchamps, Stavelot",
    "datetime_fp1": convertToTimestamp("2025-07-25 10:30"),
    "datetime_fp2": null,
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-07-26 10:00"),
    "datetime_qualifying": convertToTimestamp("2025-07-26 14:00"),
    "datetime_race": convertToTimestamp("2025-07-27 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "14",
    "name": "Hungarian Grand Prix",
    "location": "Hungaroring, Mogyoród",
    "datetime_fp1": convertToTimestamp("2025-08-01 11:30"),
    "datetime_fp2": convertToTimestamp("2025-08-01 15:00"),
    "datetime_fp3": convertToTimestamp("2025-08-02 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-08-02 14:00"),
    "datetime_race": convertToTimestamp("2025-08-03 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "15",
    "name": "Dutch Grand Prix",
    "location": "Circuit Zandvoort, Zandvoort",
    "datetime_fp1": convertToTimestamp("2025-08-29 10:30"),
    "datetime_fp2": convertToTimestamp("2025-08-29 14:00"),
    "datetime_fp3": convertToTimestamp("2025-08-30 09:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-08-30 13:00"),
    "datetime_race": convertToTimestamp("2025-08-31 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "16",
    "name": "Italian Grand Prix",
    "location": "Monza Circuit, Monza",
    "datetime_fp1": convertToTimestamp("2025-09-05 11:30"),
    "datetime_fp2": convertToTimestamp("2025-09-05 15:00"),
    "datetime_fp3": convertToTimestamp("2025-09-06 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-09-06 14:00"),
    "datetime_race": convertToTimestamp("2025-09-07 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "17",
    "name": "Azerbaijan Grand Prix",
    "location": "Baku City Circuit, Baku",
    "datetime_fp1": convertToTimestamp("2025-09-19 08:30"),
    "datetime_fp2": convertToTimestamp("2025-09-19 12:00"),
    "datetime_fp3": convertToTimestamp("2025-09-20 08:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-09-20 12:00"),
    "datetime_race": convertToTimestamp("2025-09-21 11:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "18",
    "name": "Singapore Grand Prix",
    "location": "Marina Bay Street Circuit, Singapore",
    "datetime_fp1": convertToTimestamp("2025-10-03 09:30"),
    "datetime_fp2": convertToTimestamp("2025-10-03 13:00"),
    "datetime_fp3": convertToTimestamp("2025-10-04 09:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-10-04 13:00"),
    "datetime_race": convertToTimestamp("2025-10-05 12:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "19",
    "name": "United States Grand Prix",
    "location": "Circuit of the Americas, Austin",
    "datetime_fp1": convertToTimestamp("2025-10-17 17:30"),
    "datetime_fp2": null,
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-10-18 17:00"),
    "datetime_qualifying": convertToTimestamp("2025-10-18 21:00"),
    "datetime_race": convertToTimestamp("2025-10-19 19:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "20",
    "name": "Mexico City Grand Prix",
    "location": "Autódromo Hermanos Rodríguez, Mexico City",
    "datetime_fp1": convertToTimestamp("2025-10-24 17:30"),
    "datetime_fp2": convertToTimestamp("2025-10-24 21:00"),
    "datetime_fp3": convertToTimestamp("2025-10-25 16:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-10-25 20:00"),
    "datetime_race": convertToTimestamp("2025-10-26 20:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "21",
    "name": "São Paulo Grand Prix",
    "location": "Interlagos Circuit, São Paulo",
    "datetime_fp1": convertToTimestamp("2025-11-07 13:30"),
    "datetime_fp2": null,
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-11-08 13:00"),
    "datetime_qualifying": convertToTimestamp("2025-11-08 17:00"),
    "datetime_race": convertToTimestamp("2025-11-09 16:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "22",
    "name": "Las Vegas Grand Prix",
    "location": "Las Vegas Strip Circuit, Paradise",
    "datetime_fp1": convertToTimestamp("2025-11-20 00:30"),
    "datetime_fp2": convertToTimestamp("2025-11-20 04:00"),
    "datetime_fp3": convertToTimestamp("2025-11-21 00:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-11-21 04:00"),
    "datetime_race": convertToTimestamp("2025-11-22 04:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "23",
    "name": "Qatar Grand Prix",
    "location": "Lusail International Circuit, Lusail",
    "datetime_fp1": convertToTimestamp("2025-11-28 13:30"),
    "datetime_fp2": null,
    "datetime_fp3": null,
    "datetime_sprint": convertToTimestamp("2025-11-29 13:00"),
    "datetime_qualifying": convertToTimestamp("2025-11-29 17:00"),
    "datetime_race": convertToTimestamp("2025-11-30 16:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  },
  {
    "round": "24",
    "name": "Abu Dhabi Grand Prix",
    "location": "Yas Marina Circuit, Abu Dhabi",
    "datetime_fp1": convertToTimestamp("2025-12-05 09:30"),
    "datetime_fp2": convertToTimestamp("2025-12-05 13:00"),
    "datetime_fp3": convertToTimestamp("2025-12-06 10:30"),
    "datetime_sprint": null,
    "datetime_qualifying": convertToTimestamp("2025-12-06 14:00"),
    "datetime_race": convertToTimestamp("2025-12-07 13:00"),
    "first_place": null,
    "second_place": null,
    "third_place": null
  }
];

// Function to add races to the API
async function addRaces() {
  try {
    // Clear existing races first
    console.log("Clearing existing races...");
    const clearResponse = await fetch('https://f1apibackend-1.onrender.com/api/races', {
      method: 'DELETE'
    });
    
    if (!clearResponse.ok) {
      console.warn("Warning: Could not clear existing races. Continuing with adding new races.");
    } else {
      console.log("Existing races cleared successfully.");
    }
    
    // Send each race individually
    for (const race of races) {
      console.log(`Sending race: ${race.name}`);
      
      const response = await fetch('https://f1apibackend-1.onrender.com/api/races', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(race)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Error response for ${race.name}: ${errorText}`);
        throw new Error(`HTTP error! Status: ${response.status} for race ${race.name}`);
      }

      const data = await response.json();
      console.log(`Race ${race.name} added successfully!`);
    }
    
    console.log('All races added successfully!');
  } catch (error) {
    console.error('Error adding races:', error);
  }
}

// Run the function
addRaces(); 