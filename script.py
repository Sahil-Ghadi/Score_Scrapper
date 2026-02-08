from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_stealth(page):
    """
    Manually apply stealth scripts to bypass bot detection.
    """
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    page.add_init_script("""
        window.chrome = {
            runtime: {}
        };
    """)
    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)
    page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
    """)

def get_match_data(url):
    # Data packet default structure
    empty_data = {'scorecard': [], 'meta': {
        'result': 'Error', 
        'man_of_the_match': 'N/A', 
        'match_overs': 'N/A', 
        'tournament_name': 'N/A'
    }}

    print("Launching browser for scraping...")
    with sync_playwright() as p:
        # Add args to help with sandbox issues in some environments like Streamlit Cloud
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        apply_stealth(page)
        
        print(f"Navigating to initial URL: {url}...")
        try:
            response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
            if not response:
                print("No response from page.")
            time.sleep(5) # Allow some JS to hydrate headers
        except Exception as e:
            print(f"Error loading initial page: {e}")
            browser.close()
            return empty_data

        # Attempt to get canonical URL directly from DOM
        canonical_href = page.evaluate("() => document.querySelector('link[rel=\"canonical\"]')?.href")
        
        if canonical_href:
            print(f"Canonical URL found: {canonical_href}")
            real_url = canonical_href.replace('/summary','/scorecard')
        else:
            print("Canonical link not found. Using current URL.")
            real_url = page.url
            # Helper: if user gave a summary url, force swap even if canonical missing
            if '/summary' in real_url:
                real_url = real_url.replace('/summary', '/scorecard')

        print(f"Targeting Final URL: {real_url}")
        
        # ... navigation logic ...
        # Determine if we need to navigate again
        current_url = page.url
        # Check simplified versions of URLs to avoid unnecessary reloads
        if current_url.split('?')[0] != real_url.split('?')[0]:
            print(f"Navigating to {real_url}...")
            try:
                page.goto(real_url, timeout=60000, wait_until='domcontentloaded')
                
                # Try to wait for the critical data tag, just in case
                try:
                    page.wait_for_selector('script[id="__NEXT_DATA__"]', timeout=5000)
                except:
                    print("Warning: Timed out waiting for __NEXT_DATA__ selector.")

                time.sleep(2)
            except Exception as e:
                print(f"Error loading final scorecard page: {e}")
                browser.close()
                return empty_data
        else:
            print("Already on the correct page.")
        
        content = page.content()
        page_title = page.title()
        browser.close()
        
    print(f"DEBUG: Final Page Title: {page_title}")
    
    # Save debug file for inspection
    try:
        with open("debug_last_scrape.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("DEBUG: Saved page content to debug_last_scrape.html")
    except Exception as e:
        print(f"Warning: Could not save debug HTML: {e}")

    soup = BeautifulSoup(content, 'html.parser')

    # Extract the __NEXT_DATA__ JSON blob
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    if not next_data_script:
        print("Detailed Error: Could not find __NEXT_DATA__ script tag.")
        # Bot detection check
        text_preview = soup.get_text()[:500].lower()
        if "challenge" in text_preview or "security" in text_preview:
            print("CRITICAL: Detected potential security challenge/blocking.")
        elif "enable javascript" in text_preview:
            print("CRITICAL: Page requesting JS enable (possible scraped mode detection).")
        
        return empty_data
        
    try:
        data = json.loads(next_data_script.string)
    except json.JSONDecodeError:
        print("Error: Failed to parse __NEXT_DATA__ JSON.")
        return empty_data

    # Navigate to the summary data
    try:
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        
        # Debug structure
        print(f"DEBUG: Found pageProps keys: {list(page_props.keys())}")
        
        scorecard = page_props.get('scorecard', [])
        
        # Defensive extraction for summaryData
        summary_obj = page_props.get('summaryData')
        if summary_obj is None: 
            summary_obj = {}
        summary_data = summary_obj.get('data')
        if summary_data is None: 
            summary_data = {}
        
        # Extract specific meta fields from summaryData
        match_summary = summary_data.get('match_summary')
        if match_summary is None: 
            match_summary = {}
            
        player_of_match = summary_data.get('player_of_the_match')
        if player_of_match is None: 
            player_of_match = {}
            
        tournament_name_str = summary_data.get('tournament_name', 'N/A')
        
        meta_info = {
            'result': match_summary.get('summary', 'Match Ended'),
            'man_of_the_match': player_of_match.get('player_name', 'N/A'),
            'match_overs': summary_data.get('overs', 'N/A'),
            'tournament_name': tournament_name_str
        }

    except Exception as e:
        print(f"Error extracting meta data: {e}")
        # Fallback if extraction fails
        scorecard = data.get('props', {}).get('pageProps', {}).get('scorecard', [])
        meta_info = {
            'result': 'Match Ended',
            'man_of_the_match': 'N/A',
            'match_overs': 'N/A',
            'tournament_name': 'N/A'
        }
        
    return {'scorecard': scorecard, 'meta': meta_info}

def generate_pdf(data_packet, output_file="scorecard.pdf"):
    match_data = data_packet.get('scorecard', [])
    meta_info = data_packet.get('meta', {})
    
    # Helper to parse date
    date_str = "N/A"
    time_str = "N/A"
    try:
        if match_data and len(match_data) > 0:
            start_time = match_data[0].get('inning', {}).get('inning_start_time', '')
            if start_time:
                # Basic parsing, can be improved
                date_part, time_part = start_time.split('T')
                date_str = date_part
                time_str = time_part[:5] # HH:MM
    except:
        pass

    # Teams
    team1_name = match_data[0].get('teamName', 'Team A') if len(match_data) > 0 else 'Team A'
    team2_name = match_data[1].get('teamName', 'Team B') if len(match_data) > 1 else 'Team B'
    match_title = f"{team1_name} V/S {team2_name}"
    match_overs = meta_info.get('match_overs', 'N/A')
    tournament_name = meta_info.get('tournament_name', 'N/A')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Official Match Report</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap');
            @page {{
                size: A4;
                margin: 0;
            }}
            body {{
                font-family: 'Roboto', sans-serif;
                margin: 0;
                padding: 20px 30px;
                color: #111;
                background-color: #fff;
                box-sizing: border-box;
            }}
            .container {{
                max-width: 100%;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 10px;
                text-transform: uppercase;
                border-bottom: 3px solid #000;
                padding-bottom: 10px;
            }}
            .header h1 {{ margin: 0 0 5px 0; font-size: 24px; font-weight: 900; letter-spacing: 1px; }}
            .header h2 {{ margin: 0; font-size: 16px; font-weight: 500; color: #333; }}
            
            .meta-section {{
                display: flex;
                justify-content: space-between;
                font-size: 14px;
                font-weight: 700;
                margin-bottom: 15px;
                padding: 10px;
                background-color: #f4f4f4;
                border: 2px solid #000;
            }}
            
            .match-title {{
                text-align: center;
                font-size: 18px;
                font-weight: 900;
                margin: 15px 0;
                padding: 10px;
                border: 2px solid #000;
                background-color: #fff;
                box-shadow: 3px 3px 0px #000;
            }}
            
            .inning-section {{
                margin-bottom: 20px;
            }}
            
            .inning-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 12px;
                background: #000;
                color: #fff;
                font-size: 16px;
                font-weight: 900;
                margin-bottom: 0; 
                border: 2px solid #000;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            
            th {{
                background-color: #e0e0e0;
                color: #000;
                padding: 6px;
                text-align: center;
                font-weight: 800;
                font-size: 12px;
                text-transform: uppercase;
                border: 2px solid #000;
            }}
            
            td {{
                padding: 6px;
                text-align: center;
                border: 2px solid #000;
                font-size: 14px;
                font-weight: 700;
            }}
            
            .col-no {{ width: 40px; color: #444; font-size: 12px; }}
            .col-name {{ 
                text-align: left; 
                padding-left: 10px; 
                font-size: 14px; 
                font-weight: 800;
                width: 45%;
            }}
            
            .bowling-header {{
                font-size: 14px;
                font-weight: 900;
                margin: 15px 0 5px 0;
                text-transform: uppercase;
                padding-left: 10px;
                border-left: 5px solid #000;
                line-height: 1;
            }}
            
            .footer {{
                margin-top: 20px;
                padding-top: 15px;
            }}
            
            .footer-row {{
                font-size: 14px;
                font-weight: 900;
                margin-bottom: 10px;
                padding: 10px;
                background: #f4f4f4;
                border: 2px solid #000;
            }}
            
            .label {{
                font-weight: 700;
                color: #555;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Match Scorecard</h1>
                <h2>{tournament_name}</h2>
            </div>
            
            <div class="meta-section">
                <span>DATE: {date_str}</span>
                <span>TIME: {time_str}</span>
                <span>MATCH: {match_overs} Overs</span>
            </div>
            
            <div class="match-title">
                {match_title}
            </div>
    """

    for i, inning in enumerate(match_data):
        team_name = inning.get('teamName', 'Unknown')
        inning_data = inning.get('inning', {})
        score_str = inning_data.get('summary', {}).get('score', '0/0')
        overs_played = inning_data.get('summary', {}).get('over', '')
        
        # Determine opponent name for "Bowling of..."
        opponent_index = 1 - i
        opponent_name = match_data[opponent_index].get('teamName', 'Opponent') if len(match_data) > 1 else "Opponent"

        # Batting Processing (Top 3)
        batters = inning.get('batting', [])
        # Sort by runs descending
        batters.sort(key=lambda x: int(x.get('runs', 0)), reverse=True)
        top_batters = batters[:3]

        # Bowling Processing (Top 3)
        # Find bowlers from this inning data (which lists bowlers against this batting team)
        bowlers = inning.get('bowling', [])
        # Sort by wickets desc, then runs asc (economy implicit)
        bowlers.sort(key=lambda x: (int(x.get('wickets', 0)), -int(x.get('runs', 0))), reverse=True)
        top_bowlers = bowlers[:3]

        html_content += f"""
            <div class="inning-section">
                <div class="inning-header">
                    <span>{team_name}</span>
                    <span>{score_str} {overs_played}</span>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th class="col-no">No</th>
                            <th class="col-name">BATSMAN</th>
                            <th>RUNS (BALLS)</th>
                            <th>6s</th>
                            <th>4s</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Fill Batting Rows (Always 3 rows)
        for idx in range(3):
            if idx < len(top_batters):
                b = top_batters[idx]
                no_str = f"0{idx+1}"
                name = b.get('name', '')
                runs = b.get('runs', 0)
                balls = b.get('balls', 0)
                sixes = b.get('6s', 0)
                fours = b.get('4s', 0)
                runs_display = f"{runs} ({balls})"
            else:
                no_str = f"0{idx+1}"
                name = "&nbsp;"
                runs_display = "&nbsp;"
                sixes = "&nbsp;"
                fours = "&nbsp;"
            
            html_content += f"""
                        <tr>
                            <td class="col-no">{no_str}</td>
                            <td class="col-name">{name}</td>
                            <td>{runs_display}</td>
                            <td>{sixes}</td>
                            <td>{fours}</td>
                        </tr>
            """

        html_content += f"""
                    </tbody>
                </table>
                
                <div class="bowling-header">Bowling of: {opponent_name}</div>
                <table>
                    <thead>
                        <tr>
                            <th class="col-no">No</th>
                            <th class="col-name">BOWLER</th>
                            <th>OVERS</th>
                            <th>RUNS</th>
                            <th>WKTS</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Fill Bowling Rows (Always 3 rows)
        for idx in range(3):
            if idx < len(top_bowlers):
                b = top_bowlers[idx]
                no_str = f"0{idx+1}"
                name = b.get('name', '')
                overs = b.get('overs', 0)
                runs = b.get('runs', 0)
                wkts = b.get('wickets', 0)
            else:
                no_str = f"0{idx+1}"
                name = "&nbsp;"
                overs = "&nbsp;"
                runs = "&nbsp;"
                wkts = "&nbsp;"
                
            html_content += f"""
                        <tr>
                            <td class="col-no">{no_str}</td>
                            <td class="col-name">{name}</td>
                            <td>{overs}</td>
                            <td>{runs}</td>
                            <td>{wkts}</td>
                        </tr>
            """
            
        html_content += """
                    </tbody>
                </table>
            </div>
        """

    result_text = meta_info.get('result', 'N/A')
    motm_text = meta_info.get('man_of_the_match', 'N/A')

    html_content += f"""
            <div class="footer">
                <div class="footer-row"><span class="label">RESULT:</span> {result_text}</div>
                <div class="footer-row"><span class="label">MAN OF THE MATCH:</span> {motm_text}</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    print("Generating PDF from HTML using Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content)
        # Reduce margins to allow fitting on one page
        page.pdf(path=output_file, format="A4", print_background=True, margin={"top": "0.5cm", "right": "0.5cm", "bottom": "0.5cm", "left": "0.5cm"})
        browser.close()
    
    print(f"PDF saved to {output_file}")

def run():
    url = os.getenv("MATCH_URL")
    if not url:
        print("Error: MATCH_URL environment variable not set.")
        return
        
    try:
        data_packet = get_match_data(url)
        print("Data extraction successful.")
        
        generate_pdf(data_packet, "scorecard.pdf")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()
