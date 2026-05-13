import argparse
import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gStyle.SetOptStat(0)

parser = argparse.ArgumentParser(description="Plot OverlapAnalyzer d0 histograms")
parser.add_argument("input", help="Input ROOT file (hist.root)")
parser.add_argument("-o", "--output", default="overlap_d0.pdf", help="Output file")
args = parser.parse_args()

f = ROOT.TFile.Open(args.input)
if not f or f.IsZombie():
    raise RuntimeError(f"Could not open {args.input}")

h_prompt    = f.Get("prompt_d0")
h_displaced = f.Get("displaced_d0")
for h, name in [(h_prompt, "prompt_d0"), (h_displaced, "displaced_d0")]:
    if not h:
        raise RuntimeError(f"Histogram '{name}' not found in {args.input}")
    h.SetDirectory(0)
f.Close()

h_prompt.SetLineColor(ROOT.kBlue)
h_prompt.SetLineWidth(2)

h_displaced.SetLineColor(ROOT.kRed)
h_displaced.SetLineWidth(2)

canvas = ROOT.TCanvas("c", "Overlap d0", 800, 600)
canvas.SetLogy()

ymax = max(h_prompt.GetMaximum(), h_displaced.GetMaximum()) * 5
h_prompt.SetMaximum(ymax)
h_prompt.SetMinimum(0.5)

h_prompt.GetXaxis().SetTitle("|d_{0}| [cm]")
h_prompt.GetYaxis().SetTitle("Matched muon pairs")
h_prompt.SetTitle("Muons matched between slimmedMuons and slimmedDisplacedMuons")

h_prompt.Draw("hist")
h_displaced.Draw("hist same")

legend = ROOT.TLegend(0.55, 0.75, 0.88, 0.88)
legend.AddEntry(h_prompt,    "slimmedMuons",         "l")
legend.AddEntry(h_displaced, "slimmedDisplacedMuons", "l")
legend.SetBorderSize(0)
legend.Draw()

n_prompt    = h_prompt.GetEntries()
n_displaced = h_displaced.GetEntries()
label = ROOT.TLatex()
label.SetNDC()
label.SetTextSize(0.033)
label.DrawLatex(0.55, 0.70, f"Matched pairs: {int(n_prompt)}")

canvas.SaveAs(args.output)
print(f"Saved {args.output}")
