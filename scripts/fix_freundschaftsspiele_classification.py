#!/usr/bin/env python3
"""
Korrigiere falsch klassifizierte Freundschaftsspiele in der Datenbank.

Dieses Script:
1. Erstellt den Wettbewerb "Freundschaftsspiele" falls nicht vorhanden
2. Findet alle falsch als "Europapokal" klassifizierten Spiele aus profirest.html
3. Erstellt neue season_competition Einträge für "Freundschaftsspiele"
4. Aktualisiert die Matches, um sie dem korrekten Wettbewerb zuzuordnen
"""
import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()
from backend.config import Config

def main(dry_run=True):
    config = Config()
    conn = psycopg2.connect(config.build_psycopg2_dsn())
    
    print("=" * 80)
    print(f"{'DRY RUN - ' if dry_run else ''}KORREKTUR: Falsch klassifizierte Freundschaftsspiele")
    print("=" * 80)
    
    with conn.cursor() as cur:
        # 1. Erstelle Wettbewerb "Freundschaftsspiele" falls nicht vorhanden
        print("\n1. Prüfe Wettbewerb 'Freundschaftsspiele'...")
        cur.execute("""
            SELECT competition_id FROM public.competitions WHERE name = 'Freundschaftsspiele'
        """)
        result = cur.fetchone()
        
        if result:
            freundschafts_competition_id = result[0]
            print(f"   ✓ Wettbewerb 'Freundschaftsspiele' existiert bereits (ID: {freundschafts_competition_id})")
        else:
            if dry_run:
                print("   → Würde Wettbewerb 'Freundschaftsspiele' erstellen")
                # Für Dry-Run verwenden wir eine temporäre ID (wird nicht verwendet, nur für Logik)
                freundschafts_competition_id = -1
            else:
                cur.execute("""
                    INSERT INTO public.competitions (name, normalized_name, level, gender)
                    VALUES ('Freundschaftsspiele', 'freundschaftsspiele', 'friendly', 'male')
                    RETURNING competition_id
                """)
                freundschafts_competition_id = cur.fetchone()[0]
                conn.commit()
                print(f"   ✓ Wettbewerb 'Freundschaftsspiele' erstellt (ID: {freundschafts_competition_id})")
        
        # 2. Finde falsch klassifizierte Spiele
        print("\n2. Finde falsch klassifizierte Spiele...")
        cur.execute("""
            SELECT 
                m.match_id,
                s.label AS saison,
                sc.season_id,
                sc.season_competition_id AS alte_season_competition_id,
                t_home.name AS heimmannschaft,
                t_away.name AS gastmannschaft,
                m.source_file
            FROM public.matches m
            JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
            JOIN public.seasons s ON sc.season_id = s.season_id
            JOIN public.competitions c ON sc.competition_id = c.competition_id
            JOIN public.teams t_home ON m.home_team_id = t_home.team_id
            JOIN public.teams t_away ON m.away_team_id = t_away.team_id
            WHERE c.name = 'Europapokal'
              AND m.source_file LIKE '%profirest%'
            ORDER BY s.label, m.match_id
        """)
        
        falsche_spiele = cur.fetchall()
        print(f"   Gefunden: {len(falsche_spiele)} falsch klassifizierte Spiele")
        
        if not falsche_spiele:
            print("\n✓ Keine falsch klassifizierten Spiele gefunden!")
            conn.close()
            return
        
        # Zeige erste 10
        print("\n   Erste 10 Beispiele:")
        for row in falsche_spiele[:10]:
            match_id, saison, season_id, alte_sc_id, heim, gast, source = row
            print(f"     {saison}: {heim} vs {gast} (Match ID: {match_id}, Source: {source})")
        
        # 3. Gruppiere nach Saison
        print("\n3. Gruppiere nach Saison...")
        saisonen = {}
        for row in falsche_spiele:
            match_id, saison, season_id, alte_sc_id, heim, gast, source = row
            if saison not in saisonen:
                saisonen[saison] = {
                    'season_id': season_id,
                    'matches': []
                }
            saisonen[saison]['matches'].append(match_id)
        
        print(f"   Betroffene Saisons: {', '.join(saisonen.keys())}")
        
        # 4. Erstelle season_competition Einträge für jede Saison
        print("\n4. Erstelle season_competition Einträge...")
        saison_competition_mapping = {}
        
        for saison, data in saisonen.items():
            season_id = data['season_id']
            
            # Prüfe ob bereits existiert (nur wenn Wettbewerb existiert)
            if freundschafts_competition_id > 0:
                cur.execute("""
                    SELECT season_competition_id 
                    FROM public.season_competitions
                    WHERE season_id = %s AND competition_id = %s
                """, (season_id, freundschafts_competition_id))
                
                result = cur.fetchone()
                if result:
                    sc_id = result[0]
                    print(f"   ✓ {saison}: season_competition existiert bereits (ID: {sc_id})")
                else:
                    if dry_run:
                        print(f"   → {saison}: Würde season_competition erstellen")
                        sc_id = None
                    else:
                        cur.execute("""
                            INSERT INTO public.season_competitions 
                            (season_id, competition_id, stage_label, source_path)
                            VALUES (%s, %s, %s, %s)
                            RETURNING season_competition_id
                        """, (season_id, freundschafts_competition_id, 'Freundschaftsspiele', 'profirest.html'))
                        sc_id = cur.fetchone()[0]
                        conn.commit()
                        print(f"   ✓ {saison}: season_competition erstellt (ID: {sc_id})")
            else:
                # Dry-Run: Wettbewerb existiert noch nicht
                sc_id = None
                print(f"   → {saison}: Würde season_competition erstellen (nach Wettbewerb-Erstellung)")
            
            saison_competition_mapping[saison] = sc_id
        
        # 5. Update Matches
        if not dry_run:
            print("\n5. Aktualisiere Matches...")
            updated = 0
            for saison, data in saisonen.items():
                sc_id = saison_competition_mapping[saison]
                if not sc_id:
                    print(f"   ⚠️  {saison}: Keine season_competition_id, überspringe")
                    continue
                    
                match_ids = data['matches']
                
                cur.execute("""
                    UPDATE public.matches
                    SET season_competition_id = %s
                    WHERE match_id = ANY(%s)
                """, (sc_id, match_ids))
                
                updated += len(match_ids)
                print(f"   ✓ {saison}: {len(match_ids)} Matches aktualisiert")
            
            conn.commit()
            print(f"\n✓ Insgesamt {updated} Matches korrigiert")
        else:
            print("\n5. Würde Matches aktualisieren...")
            total = sum(len(data['matches']) for data in saisonen.values())
            print(f"   → Würde {total} Matches aktualisieren")
    
    conn.close()
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN abgeschlossen. Führe ohne --dry-run aus, um Änderungen durchzuführen.")
    else:
        print("✓ Korrektur erfolgreich abgeschlossen!")
    print("=" * 80)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Korrigiere falsch klassifizierte Freundschaftsspiele')
    parser.add_argument('--execute', action='store_true', help='Führe Korrektur tatsächlich aus (ohne --execute ist es ein Dry-Run)')
    args = parser.parse_args()
    
    main(dry_run=not args.execute)

