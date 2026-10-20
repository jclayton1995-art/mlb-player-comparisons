// Pull FanGraphs leaderboards (2015-2026, batting + pitching) through your own browser
// and save them to your Downloads folder. FanGraphs blocks scripted clients, so this
// runs inside a real Chrome tab.
//
// How to use:
//   1. In Chrome, open https://www.fangraphs.com/leaders/major-league
//   2. Press Cmd+Option+J (opens the developer console)
//   3. If the console says "allow pasting", type: allow pasting   and press Enter
//   4. Paste this whole file, press Enter, and wait (~2-3 minutes; progress prints below)
//   5. Chrome may ask "allow multiple downloads" -> Allow
//   Result: fangraphs_bat_2015_2026.json and fangraphs_pit_2015_2026.json in ~/Downloads
(async () => {
  const YEARS = Array.from({ length: 12 }, (_, i) => 2015 + i);
  const KEEP = {
    bat: ["xMLBAMID","playerid","PlayerName","TeamNameAbb","Season","Age","Bats","G","AB","PA","H","1B","2B","3B","HR","R","RBI","BB","IBB","SO","HBP","SF","SH","GDP","SB","CS","AVG","GB","FB","LD","IFFB","IFH","BU","BUH","BB%","K%","OBP","SLG","OPS","ISO","BABIP","LD%","GB%","FB%","IFFB%","HR/FB","wOBA","wRAA","wRC","WAR","BaseRunning","Spd","wRC+","wBsR","UBR","O-Swing%","Z-Swing%","Swing%","O-Contact%","Z-Contact%","Contact%","Zone%","F-Strike%","SwStr%","CStr%","C+SwStr%","Pull%","Cent%","Oppo%","Soft%","Med%","Hard%","bipCount","xwOBA","xAVG","xSLG","pfxO-Swing%","pfxZ-Swing%","pfxSwing%","pfxO-Contact%","pfxZ-Contact%","pfxContact%","pfxZone%","AvgBatSpeed","FastSwing%","SwingLength","SquaredUpContact%","SquaredUpSwing%","BlastContact%","BlastSwing%","Swords","CompetitiveSwings","AttackAngle","AttackDirection","IdealAttackAngle%","Events","EV","LA","Barrels","Barrel%","maxEV","HardHit","HardHit%","EV90"],
    pit: ["xMLBAMID","playerid","PlayerName","TeamNameAbb","Season","Age","Throws","G","GS","IP","W","L","SV","HLD","TBF","H","HR","R","ER","BB","IBB","SO","HBP","ERA","WHIP","FIP","xFIP","SIERA","xERA","WAR","K/9","BB/9","HR/9","K%","BB%","K-BB%","AVG","BABIP","LOB%","GB%","FB%","LD%","IFFB%","HR/FB","O-Swing%","Z-Swing%","Swing%","O-Contact%","Z-Contact%","Contact%","Zone%","F-Strike%","SwStr%","CStr%","C+SwStr%","pfxO-Swing%","pfxZ-Swing%","pfxSwing%","pfxO-Contact%","pfxZ-Contact%","pfxContact%","pfxZone%","sp_stuff","sp_location","sp_pitching","FBv","Pull%","Cent%","Oppo%","Soft%","Med%","Hard%","Events","EV","LA","Barrels","Barrel%","maxEV","HardHit","HardHit%","Stf+ FA","Stf+ SI","Stf+ FC","Stf+ SL","Stf+ CU","Stf+ CH","Stf+ FS","Stf+ KC","Stf+ ST","Stf+ SV","Loc+ FA","Loc+ SI","Loc+ FC","Loc+ SL","Loc+ CU","Loc+ CH","Loc+ FS","Loc+ KC","Loc+ ST","Loc+ SV"],
  };
  const QUAL = { bat: 50, pit: 20 };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function pull(stats, year) {
    const url = `/api/leaders/major-league/data?pos=all&stats=${stats}&lg=all&qual=${QUAL[stats]}&season=${year}&season1=${year}&month=0&team=0&pageitems=100000&pagenum=1&ind=0&type=8`;
    for (let attempt = 0; attempt < 6; attempt++) {
      const r = await fetch(url);
      const t = await r.text();
      if (t.startsWith("{")) {
        const j = JSON.parse(t);
        if (j.data) return j.data;
      }
      console.log(`${stats} ${year}: status ${r.status}, waiting before retry ${attempt + 1}/6`);
      await sleep(8000 * (attempt + 1));
    }
    throw new Error(`gave up on ${stats} ${year}`);
  }

  function save(name, obj) {
    const blob = new Blob([JSON.stringify(obj)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  for (const stats of ["bat", "pit"]) {
    const rows = [];
    for (const y of YEARS) {
      const data = await pull(stats, y);
      for (const row of data) {
        const o = {};
        for (const k of KEEP[stats]) if (row[k] !== undefined) o[k] = row[k];
        if (o.Season == null) o.Season = y;
        rows.push(o);
      }
      console.log(`${stats} ${y}: ${data.length} rows (total ${rows.length})`);
      await sleep(2500);
    }
    save(`fangraphs_${stats}_2015_2026.json`, { cols: KEEP[stats], rows, pulled_at: new Date().toISOString() });
    console.log(`saved fangraphs_${stats}_2015_2026.json`);
  }
  console.log("DONE — both files are in your Downloads folder.");
})();
