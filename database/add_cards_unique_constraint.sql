-- SQL Script to add unique constraint to prevent duplicate cards
-- Run this AFTER fixing existing duplicates with fix_duplicate_cards.py

-- Option 1: Create unique index (handles NULL minutes)
CREATE UNIQUE INDEX IF NOT EXISTS cards_unique_match_player_minute_type 
ON public.cards (match_id, player_id, COALESCE(minute, -1), card_type);

-- Option 2: Alternatively, use two partial indexes for NULL and non-NULL cases
-- (More efficient but more complex)

-- For non-NULL minutes:
CREATE UNIQUE INDEX IF NOT EXISTS cards_unique_nonnull 
ON public.cards (match_id, player_id, minute, card_type)
WHERE minute IS NOT NULL;

-- For NULL minutes:
CREATE UNIQUE INDEX IF NOT EXISTS cards_unique_null 
ON public.cards (match_id, player_id, card_type)
WHERE minute IS NULL;

-- Note: Option 1 is simpler but slightly less efficient
-- Option 2 is more efficient but requires two indexes




