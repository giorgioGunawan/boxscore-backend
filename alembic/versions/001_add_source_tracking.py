"""Add source tracking and override columns to all tables

Revision ID: 001_add_source_tracking
Revises: 
Create Date: 2024-12-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_source_tracking'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to teams table
    op.add_column('teams', sa.Column('city', sa.String(50), nullable=True))
    op.add_column('teams', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('teams', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('teams', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('teams', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('teams', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('teams', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('teams', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))

    # Add columns to players table
    op.add_column('players', sa.Column('jersey_number', sa.String(5), nullable=True))
    op.add_column('players', sa.Column('height', sa.String(10), nullable=True))
    op.add_column('players', sa.Column('weight', sa.String(10), nullable=True))
    op.add_column('players', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('players', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('players', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('players', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('players', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('players', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('players', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))

    # Add columns to games table
    op.add_column('games', sa.Column('game_date', sa.Date(), nullable=True))
    op.add_column('games', sa.Column('game_time', sa.Time(), nullable=True))
    op.add_column('games', sa.Column('timezone', sa.String(30), server_default='America/New_York'))
    op.add_column('games', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('games', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('games', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('games', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('games', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('games', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('games', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))
    
    # Make nba_game_id nullable for manual entries
    # Note: SQLite doesn't support ALTER COLUMN, so we skip this for SQLite
    # For PostgreSQL, uncomment the following:
    # op.alter_column('games', 'nba_game_id', nullable=True)

    # Add columns to player_season_stats table
    op.add_column('player_season_stats', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('player_season_stats', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('player_season_stats', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('player_season_stats', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('player_season_stats', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('player_season_stats', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('player_season_stats', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))

    # Add columns to team_standings table
    op.add_column('team_standings', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('team_standings', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('team_standings', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('team_standings', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('team_standings', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('team_standings', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('team_standings', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))

    # Add columns to player_game_stats table
    op.add_column('player_game_stats', sa.Column('source', sa.String(20), server_default='api'))
    op.add_column('player_game_stats', sa.Column('is_manual_override', sa.Boolean(), server_default='0'))
    op.add_column('player_game_stats', sa.Column('override_reason', sa.Text(), nullable=True))
    op.add_column('player_game_stats', sa.Column('last_api_sync', sa.DateTime(), nullable=True))
    op.add_column('player_game_stats', sa.Column('last_manual_edit', sa.DateTime(), nullable=True))
    op.add_column('player_game_stats', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column('player_game_stats', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()))


def downgrade() -> None:
    # Remove columns from player_game_stats
    op.drop_column('player_game_stats', 'updated_at')
    op.drop_column('player_game_stats', 'created_at')
    op.drop_column('player_game_stats', 'last_manual_edit')
    op.drop_column('player_game_stats', 'last_api_sync')
    op.drop_column('player_game_stats', 'override_reason')
    op.drop_column('player_game_stats', 'is_manual_override')
    op.drop_column('player_game_stats', 'source')

    # Remove columns from team_standings
    op.drop_column('team_standings', 'updated_at')
    op.drop_column('team_standings', 'created_at')
    op.drop_column('team_standings', 'last_manual_edit')
    op.drop_column('team_standings', 'last_api_sync')
    op.drop_column('team_standings', 'override_reason')
    op.drop_column('team_standings', 'is_manual_override')
    op.drop_column('team_standings', 'source')

    # Remove columns from player_season_stats
    op.drop_column('player_season_stats', 'updated_at')
    op.drop_column('player_season_stats', 'created_at')
    op.drop_column('player_season_stats', 'last_manual_edit')
    op.drop_column('player_season_stats', 'last_api_sync')
    op.drop_column('player_season_stats', 'override_reason')
    op.drop_column('player_season_stats', 'is_manual_override')
    op.drop_column('player_season_stats', 'source')

    # Remove columns from games
    op.drop_column('games', 'updated_at')
    op.drop_column('games', 'created_at')
    op.drop_column('games', 'last_manual_edit')
    op.drop_column('games', 'last_api_sync')
    op.drop_column('games', 'override_reason')
    op.drop_column('games', 'is_manual_override')
    op.drop_column('games', 'source')
    op.drop_column('games', 'timezone')
    op.drop_column('games', 'game_time')
    op.drop_column('games', 'game_date')

    # Remove columns from players
    op.drop_column('players', 'updated_at')
    op.drop_column('players', 'created_at')
    op.drop_column('players', 'last_manual_edit')
    op.drop_column('players', 'last_api_sync')
    op.drop_column('players', 'override_reason')
    op.drop_column('players', 'is_manual_override')
    op.drop_column('players', 'source')
    op.drop_column('players', 'weight')
    op.drop_column('players', 'height')
    op.drop_column('players', 'jersey_number')

    # Remove columns from teams
    op.drop_column('teams', 'updated_at')
    op.drop_column('teams', 'created_at')
    op.drop_column('teams', 'last_manual_edit')
    op.drop_column('teams', 'last_api_sync')
    op.drop_column('teams', 'override_reason')
    op.drop_column('teams', 'is_manual_override')
    op.drop_column('teams', 'source')
    op.drop_column('teams', 'city')

