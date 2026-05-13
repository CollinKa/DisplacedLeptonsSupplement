#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "TH1F.h"

class OverlapAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
  public:
    explicit OverlapAnalyzer(const edm::ParameterSet& pset);
    ~OverlapAnalyzer();

    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

  private:
    void beginJob() override;
    void analyze(const edm::Event& event, const edm::EventSetup& eventSetup) override;
    void endJob() override;

    edm::EDGetTokenT<std::vector<pat::Muon>> promptToken_;
    edm::EDGetTokenT<std::vector<pat::Muon>> displacedToken_;

    float min_dR_;
    float min_dPtRelative_;

    edm::Service<TFileService> fs_;

    TH1F* h_prompt_d0;
    TH1F* h_displaced_d0;

    TH1F* h_promptNoOverlap_d0;
    TH1F* h_displacedFiltered_d0;

    TH1F* h_nMatchesPrompt;
    TH1F* h_nMatchesDisplaced;
};

OverlapAnalyzer::OverlapAnalyzer(const edm::ParameterSet& cfg) :
  promptToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("promptSource"))),
  displacedToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("displacedSource"))),
  min_dR_(cfg.getParameter<double>("min_dR")),
  min_dPtRelative_(cfg.getParameter<double>("min_dPtRelative")) {
}

OverlapAnalyzer::~OverlapAnalyzer() {}

void OverlapAnalyzer::beginJob() {
  h_prompt_d0    = fs_->make<TH1F>("prompt_d0",    "Prompt muon d_{0};d_{0} [cm];Entries",    100, 0, 10);
  h_displaced_d0 = fs_->make<TH1F>("displaced_d0", "Displaced muon d_{0};d_{0} [cm];Entries", 100, 0, 10);

  h_promptNoOverlap_d0   = fs_->make<TH1F>("promptNoOverlap_d0",   "Prompt (Non-Overlapping) muon d_{0};d_{0} [cm];Entries", 50, 0, 10);
  h_displacedFiltered_d0 = fs_->make<TH1F>("displacedFiltered_d0", "Displaced (Filtered) muon d_{0};d_{0} [cm];Entries",   50, 0, 10);

  h_nMatchesPrompt    = fs_->make<TH1F>("nMatchesPrompt",    "Matches per prompt muon;N matches;Entries",    10, 0, 10);
  h_nMatchesDisplaced = fs_->make<TH1F>("nMatchesDisplaced", "Matches per displaced muon;N matches;Entries", 10, 0, 10);
}

void OverlapAnalyzer::analyze(const edm::Event& event, const edm::EventSetup& eventSetup) {
  edm::Handle<std::vector<pat::Muon>> promptMuons;
  event.getByToken(promptToken_, promptMuons);

  edm::Handle<std::vector<pat::Muon>> displacedMuons;
  event.getByToken(displacedToken_, displacedMuons);

  for (unsigned int i = 0; i < promptMuons->size(); i++) {
    const pat::Muon& promptMuon = promptMuons->at(i);
    h_prompt_d0->Fill(promptMuon.dB());
  }

  for (unsigned int i = 0; i < displacedMuons->size(); i++) {
    const pat::Muon& displacedMuon = displacedMuons->at(i);
    h_displaced_d0->Fill(displacedMuon.dB());
  }

  std::vector<int> nMatchesPrompt(promptMuons->size(), 0);
  std::vector<int> nMatchesDisplaced(displacedMuons->size(), 0);

  for (unsigned int i = 0; i < promptMuons->size(); i++) {
    const pat::Muon& promptMuon = promptMuons->at(i);
    for (unsigned int j = 0; j < displacedMuons->size(); j++) {
      const pat::Muon& displacedMuon = displacedMuons->at(j);
      double dR          = deltaR(promptMuon.eta(), promptMuon.phi(), displacedMuon.eta(), displacedMuon.phi());
      double dPtRelative = fabs(promptMuon.pt() - displacedMuon.pt()) / displacedMuon.pt();
      if (dR < min_dR_ && dPtRelative < min_dPtRelative_) {
        nMatchesPrompt[i]++;
        nMatchesDisplaced[j]++;
      }
    }
  }

  for (unsigned int i = 0; i < promptMuons->size(); i++) {
    h_nMatchesPrompt->Fill(nMatchesPrompt[i]);
    if (nMatchesPrompt[i] == 0)
      h_promptNoOverlap_d0->Fill(promptMuons->at(i).dB());
  }

  for (unsigned int j = 0; j < displacedMuons->size(); j++) {
    h_nMatchesDisplaced->Fill(nMatchesDisplaced[j]);
    if (nMatchesDisplaced[j] == 0)
      h_displacedFiltered_d0->Fill(displacedMuons->at(j).dB());
  }
}

void OverlapAnalyzer::endJob() {}

void OverlapAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<edm::InputTag>("promptSource",    edm::InputTag("slimmedMuons"));
  desc.add<edm::InputTag>("displacedSource", edm::InputTag("slimmedDisplacedMuons"));
  desc.add<double>("min_dR",  0.01);
  desc.add<double>("min_dPtRelative", 0.1);
  descriptions.addDefault(desc);
}

DEFINE_FWK_MODULE(OverlapAnalyzer);
