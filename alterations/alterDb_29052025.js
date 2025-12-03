// Database alteration script - May 12, 2025
// Adds display_name column to driver_standings table

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

// Determine if we're running on Render with a persistent disk
const isRender = process.env.RENDER === 'true';
const renderDataDir = '/data'; // Render persistent disk mount point

// Choose the appropriate database path
let dbPath;
if (isRender && fs.existsSync(renderDataDir)) {
  dbPath = path.join(renderDataDir, 'f1races.db');
  console.log('Using Render persistent disk database at:', dbPath);
} else {
  dbPath = path.join(__dirname, '..', 'data', 'f1races.db');
  console.log('Using local database at:', dbPath);
}

// Connect to the database
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
    process.exit(1);
  }
  console.log('Connected to the F1 races database for alteration');
  
  // Execute each SQL statement separately
  db.serialize(() => {
    // Add datetime_end columns for each session
    // delete column fp1_datetime_end
    db.run(`ALTER TABLE races ADD COLUMN datetime_fp1_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_fp1_end column:', err);
      } else {
        console.log('Added datetime_fp1_end column');
      }
    });

    db.run(`ALTER TABLE races ADD COLUMN datetime_fp2_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_fp2_end column:', err);
      } else {
        console.log('Added datetime_fp2_end column');
      }
    });

    db.run(`ALTER TABLE races ADD COLUMN datetime_fp3_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_fp3_end column:', err);
      } else {
        console.log('Added datetime_fp3_end column');
      }
    });

    db.run(`ALTER TABLE races ADD COLUMN datetime_sprint_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_sprint_end column:', err);
      } else {
        console.log('Added datetime_sprint_end column');
      }
    });

    db.run(`ALTER TABLE races ADD COLUMN datetime_qualifying_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_qualifying_end column:', err);
      } else {
        console.log('Added datetime_qualifying_end column');
      }
    });

    db.run(`ALTER TABLE races ADD COLUMN datetime_race_end INTEGER`, (err) => {
      if (err) {
        console.error('Error adding datetime_race_end column:', err);
      } else {
        console.log('Added datetime_race_end column');
      }
    });

    // Update existing races with default end times (1.5 hours after start for practice sessions, 1 hour for qualifying, 2 hours for race)
    db.run(`
      UPDATE races 
      SET 
        datetime_fp1_end = datetime_fp1 + (90 * 60),
        datetime_fp2_end = datetime_fp2 + (90 * 60),
        datetime_fp3_end = datetime_fp3 + (90 * 60),
        datetime_sprint_end = datetime_sprint + (60 * 60),
        datetime_qualifying_end = datetime_qualifying + (60 * 60),
        datetime_race_end = datetime_race + (120 * 60)
      WHERE datetime_fp1 IS NOT NULL 
         OR datetime_fp2 IS NOT NULL 
         OR datetime_fp3 IS NOT NULL 
         OR datetime_sprint IS NOT NULL 
         OR datetime_qualifying IS NOT NULL 
         OR datetime_race IS NOT NULL
    `, (err) => {
      if (err) {
        console.error('Error updating existing races with end times:', err);
      } else {
        console.log('Updated existing races with end times');
      }
    });
  });
  
  // Close the database connection
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err.message);
    } else {
      console.log('Database connection closed');
    }
  });
});

