class OverlapAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
  public:
    explicit OverlapAnalyzer(const edm::ParameterSet& pset);
    ~OverlapAnalyzer();

    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

  private:
    void beginJob() override;
    void analyze(const edm::Event& event, const edm::EventSetup& eventSetup) override;
    void endJob() override;

    edm::InputTag promptSrc_;
    edm::InputTag displacedSrc_;

    float min_dR_;
    float min_Pt_;

    TFile* histFile_;
    TH1F* h_prompt_d0;
    TH1F* h_displaced_d0;
}

OverlapAnalyzer::OverlapAnalyzer(const ParameterSet& cfg) :
  promptSrc_ (cfg.getParameter<edm::InputTag>("promptSource")),
  displacedSrc_ (cfg.getParameter<edm::InputTag>("displacedSource")),
  min_dR_ (cfg.getParameter<float>("min_dR"),
  min_dPt_ (cfg.getParameter<float>("min_dPt") {
}

void OverlapAnalyzer::beginJob() {
  histFile_ = new TFile("hist.root", "RECREATE");
  h_prompt_d0 = new TH1F("overlap", "overlap", 0, 10000);
  h_disp_d0 = new TH1F("overlap", "overlap", 0, 10000);
}

void OverlapAnalyzer::analyze(const Event& event, const EventSetup& eventSetup) {
  edm::Handle<pat::Muon> promptMuons;
  event.getByLabel(promptSrc_, promptMuons);

  edm::Handle<pat::Muon> displacedMuons;
  event.getByLabel(displacedSrc_, displacedMuons);

  for (unsigned int i = 0; i < promptMuons->size(); i++) {
    const pat::Muon& promptMuon(promptMuons->at(i));

    for (unsigned int j = 0; j < displacedMuons->size(); j++) {
      const pat::Muon& displacedMuon(displacedMuons->at(i));
      double dR = deltaR(promptMuon.eta(), promptMuon.phi(), displacedMuon.eta(), displacedMuon.phi());
      const dPt = fabs(promptMuon.pt() - displacedMuon.pt());

      if (dR < min_dR_ && dPt < min_dPT) {
        h_prompt_d0->fill(promptMuon->dxy());
        h_displaced_d0->fill(displacedMuon->dxy());
      }
    }
  }
}

void OverlapAnalyzer::endJob() {
    histFile_->Write();
    histFile_->Close()
}
