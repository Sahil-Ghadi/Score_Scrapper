from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import time
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_stealth(page):
    """
    Enhanced stealth scripts to bypass bot detection.
    """
    page.add_init_script("""
        // Pass the Webdriver Test.
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """)
    page.add_init_script("""
        // Pass the Chrome Test.
        window.chrome = {
            runtime: {},
        };
    """)
    page.add_init_script("""
        // Pass the Plugins Length Test.
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """)
    page.add_init_script("""
        // Pass the Languages Test.
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)
    page.add_init_script("""
        // Overwrite the `platform` property.
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32',
        });
    """)
    page.add_init_script("""
        // Overwrite the `hardwareConcurrency` property.
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
        });
    """)
    page.add_init_script("""
        // Pass the Permissions Test.
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'denied' }) :
            originalQuery(parameters)
        );
    """)

def get_match_data(url):
    import sys
    
    print(f"[DEBUG] Starting get_match_data for URL: {url}", file=sys.stderr)
    
    try:
        r = requests.get(url, timeout=10)
        print(f"[DEBUG] Initial request status: {r.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[DEBUG] Initial request failed: {e}", file=sys.stderr)
        raise
    
    soup = BeautifulSoup(r.text, "html.parser")
    og_url = soup.find("meta", property="og:url")
    
    if not og_url:
        print(f"[DEBUG] No og:url meta tag found", file=sys.stderr)
        raise Exception("Could not find match URL in page")
    
    real_url = og_url['content']
    real_url = str(real_url) + '/scorecard'
    print(f"[DEBUG] Target scorecard URL: {real_url}", file=sys.stderr)

    # Enhanced headers to look more like a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/",
        "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

    content = None
    
    # Try with requests first (fast path)
    print("[DEBUG] Attempting to fetch with requests...", file=sys.stderr)
    try:
        session = requests.Session()
        # First request to get cookies
        session.get("https://www.google.com/", timeout=10)
        time.sleep(1)
        
        r2 = session.get(real_url, headers=headers, timeout=15)
        print(f"[DEBUG] Requests response status: {r2.status_code}", file=sys.stderr)
        
        if r2.status_code == 200 and "__NEXT_DATA__" in r2.text:
            print("[DEBUG] ✓ Successfully fetched with requests!", file=sys.stderr)
            content = r2.text
        else:
            print(f"[DEBUG] ✗ Requests failed (Status: {r2.status_code}). Falling back to Playwright.", file=sys.stderr)
    except Exception as e:
        print(f"[DEBUG] ✗ Requests error: {e}", file=sys.stderr)

    # Fallback to Playwright with enhanced stealth
    if not content:
        print("[DEBUG] Launching browser with stealth mode...", file=sys.stderr)
        
        with sync_playwright() as p:
            try:
                print("[DEBUG] Starting Playwright browser launch...", file=sys.stderr)
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process',  # Important for Streamlit Cloud
                        '--disable-gpu',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-web-security'
                    ]
                )
                
                print("[DEBUG] Browser launched, creating context...", file=sys.stderr)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none'
                    }
                )
                
                page = context.new_page()
                apply_stealth(page)
                
                # Visit Google first to look more human-like
                print("[DEBUG] Visiting Google first...", file=sys.stderr)
                try:
                    page.goto("https://www.google.com/", timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2)
                    print("[DEBUG] ✓ Google visit successful", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Warning: Could not visit Google: {e}", file=sys.stderr)
                
                # Now visit the target page
                print(f"[DEBUG] Navigating to target page: {real_url}", file=sys.stderr)
                
                navigation_success = False
                for attempt in range(3):
                    try:
                        print(f"[DEBUG] Navigation attempt {attempt + 1}/3...", file=sys.stderr)
                        page.goto(real_url, timeout=60000, wait_until="domcontentloaded")
                        print(f"[DEBUG] ✓ Page loaded (attempt {attempt + 1})", file=sys.stderr)
                        navigation_success = True
                        break
                    except Exception as e:
                        print(f"[DEBUG] ✗ Navigation attempt {attempt + 1} failed: {e}", file=sys.stderr)
                        if attempt < 2:
                            time.sleep(3)
                        else:
                            raise Exception(f"Failed to load page after 3 attempts: {e}")
                
                if not navigation_success:
                    raise Exception("Failed to navigate to target page")
                
                # Wait for Cloudflare to finish
                print("[DEBUG] Waiting for Cloudflare check (5s)...", file=sys.stderr)
                time.sleep(5)
                
                # Try to detect Cloudflare challenge
                print("[DEBUG] Checking for Cloudflare challenge...", file=sys.stderr)
                try:
                    page.wait_for_selector("body", timeout=10000)
                    page_text = page.content()
                    
                    if "Cloudflare" in page_text and "challenge" in page_text.lower():
                        print("[DEBUG] ⚠️ Cloudflare challenge detected. Waiting longer...", file=sys.stderr)
                        time.sleep(10)
                    else:
                        print("[DEBUG] ✓ No Cloudflare challenge detected", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Error checking for Cloudflare: {e}", file=sys.stderr)
                
                # Wait for the data
                print("[DEBUG] Waiting for __NEXT_DATA__...", file=sys.stderr)
                try:
                    page.wait_for_selector("script[id='__NEXT_DATA__']", timeout=30000)
                    print("[DEBUG] ✓ __NEXT_DATA__ found!", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] ✗ __NEXT_DATA__ not found: {e}", file=sys.stderr)
                    # Take screenshot for debugging
                    try:
                        screenshot_path = "debug_screenshot.png"
                        page.screenshot(path=screenshot_path)
                        print(f"[DEBUG] Debug screenshot saved as {screenshot_path}", file=sys.stderr)
                    except:
                        pass
                    
                    # Save page content
                    try:
                        page_content = page.content()
                        if "cloudflare" in page_content.lower():
                            raise Exception("Blocked by Cloudflare. The site is detecting automated access from Streamlit Cloud servers.")
                        else:
                            raise Exception("Could not find match data. The page structure may have changed.")
                    except Exception as inner_e:
                        raise inner_e
                
                content = page.content()
                print(f"[DEBUG] ✓ Content retrieved: {len(content)} characters", file=sys.stderr)
                
                context.close()
                browser.close()
                print("[DEBUG] Browser closed", file=sys.stderr)
                
            except Exception as e:
                print(f"[DEBUG] ✗ Playwright error: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                raise Exception(f"Failed to load page with Playwright: {e}")

    if not content:
        raise Exception("Failed to fetch content with both methods")

    print("[DEBUG] Parsing HTML content...", file=sys.stderr)
    # Parse the content
    soup = BeautifulSoup(content, 'html.parser')
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    
    if not next_data_script:
        page_title = soup.title.string if soup.title else "No Title"
        print(f"[DEBUG] ✗ Could not find __NEXT_DATA__. Page title: {page_title}", file=sys.stderr)
        
        # Save HTML for debugging
        try:
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify()[:5000])
            print("[DEBUG] Debug HTML saved (first 5000 chars)", file=sys.stderr)
        except:
            pass
        
        raise Exception(f"Could not find match data in page. Title: {page_title}")

    print("[DEBUG] Parsing JSON data...", file=sys.stderr)
    data = json.loads(next_data_script.string)

    try:
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        scorecard = page_props.get('scorecard', [])

        summary_data = page_props.get('summaryData', {}).get('data', {})

        meta_info = {
            'result': summary_data.get('match_summary', {}).get('summary', 'Match Ended'),
            'man_of_the_match': summary_data.get('player_of_the_match', {}).get('player_name', 'N/A'),
            'match_overs': summary_data.get('overs', 'N/A'),
            'tournament_name': summary_data.get('tournament_name', 'N/A')
        }
        
        print(f"[DEBUG] ✓ Data extracted successfully. Scorecard length: {len(scorecard)}", file=sys.stderr)

    except Exception as e:
        print(f"[DEBUG] ✗ Meta extraction error: {e}", file=sys.stderr)
        scorecard = []
        meta_info = {}

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
                date_part, time_part = start_time.split('T')
                date_str = date_part
                time_str = time_part[:5]
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
        
        opponent_index = 1 - i
        opponent_name = match_data[opponent_index].get('teamName', 'Opponent') if len(match_data) > 1 else "Opponent"

        # Batting Processing (Top 3)
        batters = inning.get('batting', [])
        batters.sort(key=lambda x: int(x.get('runs', 0)), reverse=True)
        top_batters = batters[:3]

        # Bowling Processing (Top 3)
        bowlers = inning.get('bowling', [])
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
    
    print("Generating PDF from HTML...")
    try:
        # Try using weasyprint first (more reliable on cloud)
        try:
            from weasyprint import HTML
            print("Using WeasyPrint for PDF generation...")
            HTML(string=html_content).write_pdf(output_file)
            print(f"✓ PDF saved to {output_file}")
            return
        except ImportError:
            print("WeasyPrint not available, using Playwright...")
        
        # Fallback to Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(
                path=output_file, 
                format="A4", 
                print_background=True, 
                margin={"top": "0.5cm", "right": "0.5cm", "bottom": "0.5cm", "left": "0.5cm"}
            )
            browser.close()
        
        print(f"✓ PDF saved to {output_file}")
    except Exception as e:
        print(f"✗ PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        raise

def run():
    url = os.getenv("MATCH_URL")
    if not url:
        print("Error: MATCH_URL environment variable not set. Please set it in .env file.")
        return
        
    try:
        print("="*60)
        print("Starting Cricket Scorecard Scraper")
        print("="*60)
        
        data_packet = get_match_data(url)
        print("\n✓ Data extraction successful.")
        
        generate_pdf(data_packet, "scorecard.pdf")
        
        print("\n" + "="*60)
        print("Process completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run()