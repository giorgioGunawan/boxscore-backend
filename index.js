const path = require('path');
const express = require('express');
const cors = require('cors');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: '*', // For development only - allows any origin
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(express.json());

// Determine if we're running on Render with a persistent disk
const isRender = process.env.RENDER === 'true';
const renderDataDir = '/data'; // Render persistent disk mount point

// Choose the appropriate database path
let dbPath;
if (isRender && fs.existsSync(renderDataDir)) {
  dbPath = path.join(renderDataDir, 'f1races.db');
  console.log('Using Render persistent disk database at:', dbPath);
} else {
  dbPath = path.join(__dirname, 'data', 'f1races.db');
  console.log('Using local database at:', dbPath);
}

// Database connection
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
    process.exit(1);
  }
  console.log('Connected to the F1 races database');

  // Add this near the beginning after database connection is established
  db.get("PRAGMA table_info(driver_standings)", (err, rows) => {
    if (err) {
      console.error('Error checking driver_standings table schema:', err);
    }
  });
});

// Routes
app.get('/', (req, res) => {
  res.send('Welcome to the F1 Race API');
});

app.get('/api/races', (req, res) => {
  db.all('SELECT * FROM races', (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

app.get('/api/nextrace', (req, res) => {
  // Get the race with the earliest upcoming race datetime
  db.get('SELECT * FROM races WHERE datetime_race >= ? ORDER BY datetime_race ASC LIMIT 1', 
    [Math.floor(Date.now() / 1000)], // Current timestamp
    (err, row) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (!row) {
        return res.status(404).json({ error: 'No upcoming races found' });
      }
      res.json(row);
    });
});

app.get('/api/races/:id', (req, res) => {
  db.get('SELECT * FROM races WHERE id = ?', [req.params.id], (err, row) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (!row) {
      return res.status(404).json({ error: 'Race not found' });
    }
    res.json(row);
  });
});

// Add a new race
app.post('/api/races', (req, res) => {
  const { 
    round,
    name, 
    location,
    shortname,
    datetime_fp1, 
    datetime_fp2, 
    datetime_fp3, 
    datetime_sprint, 
    datetime_qualifying, 
    datetime_race,
    datetime_fp1_end,
    datetime_fp2_end,
    datetime_fp3_end,
    datetime_sprint_end,
    datetime_qualifying_end,
    datetime_race_end,
    first_place_driver_id,
    second_place_driver_id,
    third_place_driver_id
  } = req.body;
  
  if (!name || !location || !datetime_race) {
    return res.status(400).json({ error: 'Please provide name, location, and race datetime at minimum' });
  }

  // First get the driver names from driver_standings
  const driverPromises = [
    first_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [first_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null),
    second_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [second_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null),
    third_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [third_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null)
  ];

  Promise.all(driverPromises)
    .then(([first_place, second_place, third_place]) => {
      db.run(`INSERT INTO races (
        round,
        name, 
        location,
        shortname,
        datetime_fp1, 
        datetime_fp2, 
        datetime_fp3, 
        datetime_sprint, 
        datetime_qualifying, 
        datetime_race,
        datetime_fp1_end,
        datetime_fp2_end,
        datetime_fp3_end,
        datetime_sprint_end,
        datetime_qualifying_end,
        datetime_race_end,
        first_place,
        second_place,
        third_place
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        round || null,
        name, 
        location,
        shortname || null,
        datetime_fp1 || null, 
        datetime_fp2 || null, 
        datetime_fp3 || null, 
        datetime_sprint || null, 
        datetime_qualifying || null, 
        datetime_race,
        datetime_fp1_end || null,
        datetime_fp2_end || null,
        datetime_fp3_end || null,
        datetime_sprint_end || null,
        datetime_qualifying_end || null,
        datetime_race_end || null,
        first_place,
        second_place,
        third_place
      ],
      function(err) {
        if (err) {
          return res.status(500).json({ error: err.message });
        }
        res.status(201).json({
          id: this.lastID,
          round,
          name,
          location,
          shortname,
          datetime_fp1,
          datetime_fp2,
          datetime_fp3,
          datetime_sprint,
          datetime_qualifying,
          datetime_race,
          datetime_fp1_end,
          datetime_fp2_end,
          datetime_fp3_end,
          datetime_sprint_end,
          datetime_qualifying_end,
          datetime_race_end,
          first_place,
          second_place,
          third_place
        });
      });
    })
    .catch(err => {
      res.status(500).json({ error: err.message });
    });
});

// Update a race
app.put('/api/races/:id', (req, res) => {
  const raceId = req.params.id;
  const {
    round,
    name,
    location,
    shortname,
    datetime_fp1,
    datetime_fp2,
    datetime_fp3,
    datetime_sprint,
    datetime_qualifying,
    datetime_race,
    datetime_fp1_end,
    datetime_fp2_end,
    datetime_fp3_end,
    datetime_sprint_end,
    datetime_qualifying_end,
    datetime_race_end,
    first_place_driver_id,
    second_place_driver_id,
    third_place_driver_id
  } = req.body;
  
  if (!name || !location || !datetime_race) {
    return res.status(400).json({ error: 'Please provide name, location, and race datetime at minimum' });
  }
  
  // First get the driver names from driver_standings
  const driverPromises = [
    first_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [first_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null),
    second_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [second_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null),
    third_place_driver_id ? new Promise((resolve, reject) => {
      db.get('SELECT driver_name FROM driver_standings WHERE id = ?', [third_place_driver_id], (err, row) => {
        if (err) reject(err);
        else resolve(row ? row.driver_name : null);
      });
    }) : Promise.resolve(null)
  ];

  Promise.all(driverPromises)
    .then(([first_place, second_place, third_place]) => {
      const query = `
        UPDATE races SET
          round = ?,
          name = ?,
          location = ?,
          shortname = ?,
          datetime_fp1 = ?,
          datetime_fp2 = ?,
          datetime_fp3 = ?,
          datetime_sprint = ?,
          datetime_qualifying = ?,
          datetime_race = ?,
          datetime_fp1_end = ?,
          datetime_fp2_end = ?,
          datetime_fp3_end = ?,
          datetime_sprint_end = ?,
          datetime_qualifying_end = ?,
          datetime_race_end = ?,
          first_place = ?,
          second_place = ?,
          third_place = ?
        WHERE id = ?
      `;

      const params = [
        round || null,
        name,
        location,
        shortname || null,
        datetime_fp1 || null,
        datetime_fp2 || null,
        datetime_fp3 || null,
        datetime_sprint || null,
        datetime_qualifying || null,
        datetime_race,
        datetime_fp1_end || null,
        datetime_fp2_end || null,
        datetime_fp3_end || null,
        datetime_sprint_end || null,
        datetime_qualifying_end || null,
        datetime_race_end || null,
        first_place,
        second_place,
        third_place,
        raceId
      ];

      db.run(query, params, function(err) {
        if (err) {
          return res.status(500).json({ error: err.message });
        }
        if (this.changes === 0) {
          return res.status(404).json({ error: 'Race not found' });
        }
        res.json({
          id: raceId,
          round,
          name,
          location,
          shortname,
          datetime_fp1,
          datetime_fp2,
          datetime_fp3,
          datetime_sprint,
          datetime_qualifying,
          datetime_race,
          datetime_fp1_end,
          datetime_fp2_end,
          datetime_fp3_end,
          datetime_sprint_end,
          datetime_qualifying_end,
          datetime_race_end,
          first_place,
          second_place,
          third_place
        });
      });
    })
    .catch(err => {
      res.status(500).json({ error: err.message });
    });
});

// Delete a race
app.delete('/api/races/:id', (req, res) => {
  db.run('DELETE FROM races WHERE id = ?', [req.params.id], function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Race not found' });
    }
    res.json({ message: 'Race deleted successfully' });
  });
});

// RESULTS TABLE ENDPOINTS
// Get all results
app.get('/api/results', (req, res) => {
  db.all('SELECT * FROM results', (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

// Get results by race_id
app.get('/api/results/race/:race_id', (req, res) => {
  db.all('SELECT * FROM results WHERE race_id = ?', [req.params.race_id], (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

// Get results by race_id and session_type
app.get('/api/results/race/:race_id/session/:session_type', (req, res) => {
  db.all('SELECT * FROM results WHERE race_id = ? AND session_type = ?', 
    [req.params.race_id, req.params.session_type], 
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    });
});

// Add a new result
app.post('/api/results', (req, res) => {
  const { 
    race_id, 
    session_type, 
    position, 
    driver_name, 
    team_name, 
    time, 
    laps, 
    points 
  } = req.body;
  
  if (!race_id || !session_type || !position || !driver_name || !team_name) {
    return res.status(400).json({ 
      error: 'Please provide race_id, session_type, position, driver_name, and team_name at minimum' 
    });
  }
  
  db.run(`INSERT INTO results (
            race_id, 
            session_type, 
            position, 
            driver_name, 
            team_name, 
            time, 
            laps, 
            points
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      race_id, 
      session_type, 
      position, 
      driver_name, 
      team_name, 
      time || null, 
      laps || null, 
      points || null
    ],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        id: this.lastID,
        race_id,
        session_type,
        position,
        driver_name,
        team_name,
        time,
        laps,
        points
      });
    });
});

// Update a result
app.put('/api/results/:id', (req, res) => {
  const { 
    race_id, 
    session_type, 
    position, 
    driver_name, 
    team_name, 
    time, 
    laps, 
    points 
  } = req.body;
  
  if (!race_id || !session_type || !position || !driver_name || !team_name) {
    return res.status(400).json({ 
      error: 'Please provide race_id, session_type, position, driver_name, and team_name at minimum' 
    });
  }
  
  db.run(`UPDATE results SET 
            race_id = ?, 
            session_type = ?, 
            position = ?, 
            driver_name = ?, 
            team_name = ?, 
            time = ?, 
            laps = ?, 
            points = ? 
          WHERE id = ?`,
    [
      race_id, 
      session_type, 
      position, 
      driver_name, 
      team_name, 
      time || null, 
      laps || null, 
      points || null,
      req.params.id
    ],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Result not found' });
      }
      res.json({
        id: parseInt(req.params.id),
        race_id,
        session_type,
        position,
        driver_name,
        team_name,
        time,
        laps,
        points
      });
    });
});

// Delete a result
app.delete('/api/results/:id', (req, res) => {
  db.run('DELETE FROM results WHERE id = ?', [req.params.id], function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Result not found' });
    }
    res.json({ message: 'Result deleted successfully' });
  });
});

// DRIVER STANDINGS ENDPOINTS
// Get all driver standings
app.get('/api/driver-standings', (req, res) => {
  db.all('SELECT * FROM driver_standings ORDER BY points DESC', (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

// Get driver standing by id
app.get('/api/driver-standings/:id', (req, res) => {
  db.get('SELECT * FROM driver_standings WHERE id = ?', [req.params.id], (err, row) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (!row) {
      return res.status(404).json({ error: 'Driver standing not found' });
    }
    res.json(row);
  });
});

// Add a new driver standing
app.post('/api/driver-standings', (req, res) => {
  const { driver_name, team_name, points, driver_number, display_name } = req.body;
  
  if (!driver_name || !team_name || points === undefined) {
    return res.status(400).json({ error: 'Please provide driver_name, team_name, and points' });
  }
  
  db.run(`INSERT INTO driver_standings (driver_name, team_name, points, driver_number, display_name) VALUES (?, ?, ?, ?, ?)`,
    [driver_name, team_name, points, driver_number || null, display_name || null],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        id: this.lastID,
        driver_name,
        team_name,
        points,
        driver_number,
        display_name
      });
    });
});

// Update a driver standing
app.put('/api/driver-standings/:id', (req, res) => {  
  const { driver_name, team_name, points, driver_number, display_name } = req.body;
  
  if (!driver_name || !team_name || points === undefined) {
    return res.status(400).json({ error: 'Please provide driver_name, team_name, and points' });
  }
    
  // First, let's check the current record in the database
  db.get('SELECT * FROM driver_standings WHERE id = ?', [req.params.id], (err, row) => {
    if (err) {
      console.error('Error fetching current record:', err);
      return res.status(500).json({ error: err.message });
    }
    
    
    // Now perform the update
    const updateQuery = `UPDATE driver_standings SET 
                          driver_name = ?, 
                          team_name = ?, 
                          points = ?, 
                          driver_number = ?, 
                          display_name = ? 
                        WHERE id = ?`;
    
    const params = [
      driver_name, 
      team_name, 
      points, 
      driver_number || null, 
      display_name, // Don't convert empty string to null
      req.params.id
    ];
    

    db.run(updateQuery, params, function(err) {
      if (err) {
        console.error('Database error during update:', err); // Debug log
        return res.status(500).json({ error: err.message });
      }
      
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Driver standing not found' });  
      }
      
      // After update, fetch the record again to confirm changes
      db.get('SELECT * FROM driver_standings WHERE id = ?', [req.params.id], (err, updatedRow) => {
        if (err) {
          console.error('Error fetching updated record:', err);
          // Still return success response even if this verification query fails
        }
        // Create the response object with the exact values that were sent
        const updatedRecord = {
          id: parseInt(req.params.id),
          driver_name,
          team_name,
          points,
          driver_number: driver_number || null,
          display_name: display_name  // Use the exact value that was sent
        };
        
        res.json(updatedRecord);
      });
    });
  });
});

// Delete a driver standing
app.delete('/api/driver-standings/:id', (req, res) => {
  db.run('DELETE FROM driver_standings WHERE id = ?', [req.params.id], function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Driver standing not found' });
    }
    res.json({ message: 'Driver standing deleted successfully' });
  });
});

// CONSTRUCTOR STANDINGS ENDPOINTS
// Get all constructor standings
app.get('/api/constructor-standings', (req, res) => {
    // First check if the new columns exist
    db.get("PRAGMA table_info(constructor_standings)", [], (err, rows) => {
        if (err) {
            res.status(500).json({ error: err.message });
            return;
        }

        // Use the appropriate query based on which columns exist
        const query = `
            SELECT cs.*, 
                d1.display_name as driver_1_display_name, 
                d1.driver_name as driver_1_name, 
                d1.team_name as driver_1_team,
                d2.display_name as driver_2_display_name, 
                d2.driver_name as driver_2_name, 
                d2.team_name as driver_2_team,
                d3.display_name as driver_3_display_name, 
                d3.driver_name as driver_3_name, 
                d3.team_name as driver_3_team
            FROM constructor_standings cs
            LEFT JOIN driver_standings d1 ON cs.driver_id_1 = d1.id
            LEFT JOIN driver_standings d2 ON cs.driver_id_2 = d2.id
            LEFT JOIN driver_standings d3 ON cs.driver_id_3 = d3.id
            ORDER BY cs.points DESC
        `;

        db.all(query, [], (err, rows) => {
            if (err) {
                res.status(500).json({ error: err.message });
                return;
            }
            res.json(rows);
        });
    });
});

// Get constructor standing by id
app.get('/api/constructor-standings/:id', (req, res) => {
    const query = `
        SELECT cs.*, 
            d1.display_name as driver_1_display_name, 
            d1.driver_name as driver_1_name, 
            d1.team_name as driver_1_team,
            d2.display_name as driver_2_display_name, 
            d2.driver_name as driver_2_name, 
            d2.team_name as driver_2_team,
            d3.display_name as driver_3_display_name, 
            d3.driver_name as driver_3_name, 
            d3.team_name as driver_3_team
        FROM constructor_standings cs
        LEFT JOIN driver_standings d1 ON cs.driver_id_1 = d1.id
        LEFT JOIN driver_standings d2 ON cs.driver_id_2 = d2.id
        LEFT JOIN driver_standings d3 ON cs.driver_id_3 = d3.id
        WHERE cs.id = ?
    `;

    db.get(query, [req.params.id], (err, row) => {
        if (err) {
            return res.status(500).json({ error: err.message });
        }
        if (!row) {
            return res.status(404).json({ error: 'Constructor standing not found' });
        }
        res.json(row);
    });
});

// Add a new constructor standing
app.post('/api/constructor-standings', (req, res) => {
    const { constructor_name, points, driver_id_1, driver_id_2, driver_id_3 } = req.body;
    db.run(`
        INSERT INTO constructor_standings (constructor_name, points, driver_id_1, driver_id_2, driver_id_3)
        VALUES (?, ?, ?, ?, ?)
    `, [constructor_name, points, driver_id_1, driver_id_2, driver_id_3], function(err) {
        if (err) {
            res.status(500).json({ error: err.message });
            return;
        }
        res.json({ id: this.lastID });
    });
});

// Update a constructor standing
app.put('/api/constructor-standings/:id', (req, res) => {
    const { constructor_name, points, driver_id_1, driver_id_2, driver_id_3 } = req.body;
    
    // Convert driver IDs to integers or null
    const driverId1 = driver_id_1 ? parseInt(driver_id_1) : null;
    const driverId2 = driver_id_2 ? parseInt(driver_id_2) : null;
    const driverId3 = driver_id_3 ? parseInt(driver_id_3) : null;
    
    db.run(
        `UPDATE constructor_standings 
         SET constructor_name = ?, 
             points = ?, 
             driver_id_1 = ?, 
             driver_id_2 = ?, 
             driver_id_3 = ? 
         WHERE id = ?`,
        [constructor_name, points, driverId1, driverId2, driverId3, req.params.id],
        function(err) {
            if (err) {
                console.error('Database error:', err);
                return res.status(500).json({ error: err.message });
            }
            if (this.changes === 0) {
                return res.status(404).json({ error: 'Constructor standing not found' });
            }
            // Return the updated data
            db.get(
                `SELECT cs.*, 
                    d1.display_name as driver_1_display_name, d1.driver_name as driver_1_name,
                    d2.display_name as driver_2_display_name, d2.driver_name as driver_2_name,
                    d3.display_name as driver_3_display_name, d3.driver_name as driver_3_name
                FROM constructor_standings cs
                LEFT JOIN driver_standings d1 ON cs.driver_id_1 = d1.id
                LEFT JOIN driver_standings d2 ON cs.driver_id_2 = d2.id
                LEFT JOIN driver_standings d3 ON cs.driver_id_3 = d3.id
                WHERE cs.id = ?`,
                [req.params.id],
                (err, row) => {
                    if (err) {
                        return res.status(500).json({ error: err.message });
                    }
                    res.json(row);
                }
            );
        }
    );
});

// Delete a constructor standing
app.delete('/api/constructor-standings/:id', (req, res) => {
  db.run('DELETE FROM constructor_standings WHERE id = ?', [req.params.id], function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Constructor standing not found' });
    }
    res.json({ message: 'Constructor standing deleted successfully' });
  });
});

// LIVE RACE ENDPOINTS
// Get all live race data
app.get('/api/live-race', (req, res) => {
  db.all('SELECT * FROM live_race ORDER BY position ASC', (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json(rows);
  });
});

// Get live race entry by id
app.get('/api/live-race/:id', (req, res) => {
  db.get('SELECT * FROM live_race WHERE id = ?', [req.params.id], (err, row) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (!row) {
      return res.status(404).json({ error: 'Live race entry not found' });
    }
    res.json(row);
  });
});

// Add a new live race entry
app.post('/api/live-race', (req, res) => {
  const { 
    driver_name, 
    team_name, 
    car_number, 
    position, 
    time_behind, 
    current_lap, 
    is_dnf 
  } = req.body;
  
  if (!driver_name || !team_name || !car_number || position === undefined) {
    return res.status(400).json({ 
      error: 'Please provide driver_name, team_name, car_number, and position at minimum' 
    });
  }
  
  db.run(`INSERT INTO live_race (
            driver_name, 
            team_name, 
            car_number, 
            position, 
            time_behind, 
            current_lap, 
            is_dnf
          ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [
      driver_name, 
      team_name, 
      car_number, 
      position, 
      time_behind || null, 
      current_lap || null, 
      is_dnf || 0
    ],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.status(201).json({
        id: this.lastID,
        driver_name,
        team_name,
        car_number,
        position,
        time_behind,
        current_lap,
        is_dnf: is_dnf || 0
      });
    });
});

// Update a live race entry
app.put('/api/live-race/:id', (req, res) => {
  const { 
    driver_name, 
    team_name, 
    car_number, 
    position, 
    time_behind, 
    current_lap, 
    is_dnf 
  } = req.body;
  
  if (!driver_name || !team_name || !car_number || position === undefined) {
    return res.status(400).json({ 
      error: 'Please provide driver_name, team_name, car_number, and position at minimum' 
    });
  }
  
  db.run(`UPDATE live_race SET 
            driver_name = ?, 
            team_name = ?, 
            car_number = ?, 
            position = ?, 
            time_behind = ?, 
            current_lap = ?, 
            is_dnf = ? 
          WHERE id = ?`,
    [
      driver_name, 
      team_name, 
      car_number, 
      position, 
      time_behind || null, 
      current_lap || null, 
      is_dnf || 0,
      req.params.id
    ],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Live race entry not found' });
      }
      res.json({
        id: parseInt(req.params.id),
        driver_name,
        team_name,
        car_number,
        position,
        time_behind,
        current_lap,
        is_dnf: is_dnf || 0
      });
    });
});

// Delete a live race entry
app.delete('/api/live-race/:id', (req, res) => {
  db.run('DELETE FROM live_race WHERE id = ?', [req.params.id], function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Live race entry not found' });
    }
    res.json({ message: 'Live race entry deleted successfully' });
  });
});

// Clear all live race data
app.delete('/api/live-race', (req, res) => {
  db.run('DELETE FROM live_race', function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json({ message: 'All live race data cleared successfully' });
  });
});

// Update race with podium results
app.put('/api/races/:id/podium', (req, res) => {
  const { first_place, second_place, third_place } = req.body;
  
  if (!first_place || !second_place || !third_place) {
    return res.status(400).json({ error: 'Please provide first_place, second_place, and third_place' });
  }
  
  db.run(`UPDATE races SET first_place = ?, second_place = ?, third_place = ? WHERE id = ?`,
    [first_place, second_place, third_place, req.params.id],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Race not found' });
      }
      res.json({
        id: parseInt(req.params.id),
        first_place,
        second_place,
        third_place
      });
    });
});

// Delete all races
app.delete('/api/races', (req, res) => {
  db.run('DELETE FROM races', function(err) {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    res.json({ message: 'All races deleted successfully' });
  });
});

// Get all upcoming races (where race end time is in the future)
app.get('/api/upcoming-races', (req, res) => {
  const currentTimestamp = Math.floor(Date.now() / 1000); // Current time in Unix timestamp
  
  db.all(
    'SELECT * FROM races WHERE datetime_race_end >= ? ORDER BY datetime_race ASC',
    [currentTimestamp],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      res.json(rows);
    }
  );
});

// Get latest race result with detailed winner information
app.get('/api/latest-result', (req, res) => {
  const currentTimestamp = Math.floor(Date.now() / 1000);

  // First get the most recent completed race
  db.get(
    `SELECT 
      id as race_id,
      round,
      name,
      location,
      shortname,
      first_place,
      second_place,
      third_place
    FROM races 
    WHERE datetime_race_end < ? 
    ORDER BY datetime_race_end DESC 
    LIMIT 1`,
    [currentTimestamp],
    (err, race) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }

      // If no completed race is found, return null values
      if (!race) {
        return res.json({
          race_id: null,
          round: null,
          name: null,
          location: null,
          shortname: null,
          first_place_winner_id: null,
          first_place_winner_name: null,
          first_place_winner_team: null,
          first_place_winner_driver_number: null,
          first_place_winner_display_name: null,
          second_place_winner_id: null,
          second_place_winner_name: null,
          second_place_winner_team: null,
          second_place_winner_driver_number: null,
          second_place_winner_display_name: null,
          third_place_winner_id: null,
          third_place_winner_name: null,
          third_place_winner_team: null,
          third_place_winner_driver_number: null,
          third_place_winner_display_name: null
        });
      }

      // Get driver details for all three podium positions
      const driverPromises = [
        // First place
        race.first_place ? new Promise((resolve, reject) => {
          db.get(
            'SELECT id, driver_name, team_name, driver_number, display_name FROM driver_standings WHERE driver_name = ?',
            [race.first_place],
            (err, driver) => {
              if (err) reject(err);
              else resolve(driver);
            }
          );
        }) : Promise.resolve(null),
        // Second place
        race.second_place ? new Promise((resolve, reject) => {
          db.get(
            'SELECT id, driver_name, team_name, driver_number, display_name FROM driver_standings WHERE driver_name = ?',
            [race.second_place],
            (err, driver) => {
              if (err) reject(err);
              else resolve(driver);
            }
          );
        }) : Promise.resolve(null),
        // Third place
        race.third_place ? new Promise((resolve, reject) => {
          db.get(
            'SELECT id, driver_name, team_name, driver_number, display_name FROM driver_standings WHERE driver_name = ?',
            [race.third_place],
            (err, driver) => {
              if (err) reject(err);
              else resolve(driver);
            }
          );
        }) : Promise.resolve(null)
      ];

      Promise.all(driverPromises)
        .then(([first, second, third]) => {
          res.json({
            race_id: race.race_id,
            round: race.round,
            name: race.name,
            location: race.location,
            shortname: race.shortname,
            // First place details
            first_place_winner_id: first ? first.id : null,
            first_place_winner_name: race.first_place || null,
            first_place_winner_team: first ? first.team_name : null,
            first_place_winner_driver_number: first ? first.driver_number : null,
            first_place_winner_display_name: first ? first.display_name : null,
            // Second place details
            second_place_winner_id: second ? second.id : null,
            second_place_winner_name: race.second_place || null,
            second_place_winner_team: second ? second.team_name : null,
            second_place_winner_driver_number: second ? second.driver_number : null,
            second_place_winner_display_name: second ? second.display_name : null,
            // Third place details
            third_place_winner_id: third ? third.id : null,
            third_place_winner_name: race.third_place || null,
            third_place_winner_team: third ? third.team_name : null,
            third_place_winner_driver_number: third ? third.driver_number : null,
            third_place_winner_display_name: third ? third.display_name : null
          });
        })
        .catch(err => {
          res.status(500).json({ error: err.message });
        });
    }
  );
});

// Serve static files from the 'public' directory
app.use(express.static('public'));

// Add a route for the admin dashboard
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.listen(PORT, () => {
  console.log(`F1 API running on http://localhost:${PORT}`);
});

// Close database connection when app terminates
process.on('SIGINT', () => {
  db.close((err) => {
    if (err) {
      console.error(err.message);
    }
    console.log('Database connection closed');
    process.exit(0);
  });
});
