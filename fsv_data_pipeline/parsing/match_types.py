from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class PlayerAppearance:
    name: str
    shirt_number: Optional[int]
    is_starter: bool
    profile_url: Optional[str] = None
    minute_on: Optional[int] = None
    stoppage_on: Optional[int] = None
    minute_off: Optional[int] = None
    stoppage_off: Optional[int] = None
    card_events: List[Tuple[Optional[int], Optional[int], str]] = field(default_factory=list)


@dataclass
class GoalEvent:
    minute: Optional[int]
    stoppage: Optional[int]
    score_home: int
    score_away: int
    scorer: str
    assist: Optional[str]
    team_role: str
    scorer_profile_url: Optional[str] = None
    assist_profile_url: Optional[str] = None
    is_penalty: bool = False
    is_own_goal: bool = False


@dataclass
class MatchMetadata:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    half_home: Optional[int] = None
    half_away: Optional[int] = None
    date: Optional[str] = None
    kickoff: Optional[str] = None
    attendance: Optional[int] = None
    referee: Optional[str] = None
    referee_link: Optional[str] = None
    home_coach: Optional[str] = None
    home_coach_link: Optional[str] = None
    away_coach: Optional[str] = None
    away_coach_link: Optional[str] = None
    stage_label: Optional[str] = None
    matchday: Optional[int] = None
    round_name: Optional[str] = None
    leg: Optional[int] = None
