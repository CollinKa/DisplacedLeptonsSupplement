#include "MuonTimingAnalyzer.h"
#include "FWCore/Framework/interface/MakerMacros.h"

MuonTimingAnalyzer::MuonTimingAnalyzer(const edm::ParameterSet &iConfig) :
  muonToken_    (consumes<std::vector<pat::Muon>>     (iConfig.getParameter<edm::InputTag>("muonSrc"))),
  electronToken_(consumes<std::vector<pat::Electron>> (iConfig.getParameter<edm::InputTag>("electronSrc")))
{}

void MuonTimingAnalyzer::beginJob() {
  tree_ = fs_->make<TTree>("muonTree", "muonTree");

  tree_->Branch("run",             &run_);
  tree_->Branch("luminosityBlock", &lumi_);
  tree_->Branch("event",           &event_);

  tree_->Branch("muon_pt",             &muon_pt_);
  tree_->Branch("muon_eta",            &muon_eta_);
  tree_->Branch("muon_phi",            &muon_phi_);
  tree_->Branch("muon_timeAtIpInOut",  &muon_timeAtIpInOut_);
  tree_->Branch("muon_timeNDof",       &muon_timeNDof_);

  tree_->Branch("electron_pt",  &electron_pt_);
  tree_->Branch("electron_eta", &electron_eta_);
  tree_->Branch("electron_phi", &electron_phi_);
}

void MuonTimingAnalyzer::analyze(const edm::Event &iEvent, const edm::EventSetup &) {
  run_   = iEvent.id().run();
  lumi_  = iEvent.luminosityBlock();
  event_ = iEvent.id().event();

  muon_pt_.clear(); muon_eta_.clear(); muon_phi_.clear();
  muon_timeAtIpInOut_.clear(); muon_timeNDof_.clear();
  electron_pt_.clear(); electron_eta_.clear(); electron_phi_.clear();

  edm::Handle<std::vector<pat::Muon>> muons;
  iEvent.getByToken(muonToken_, muons);
  for (const auto &mu : *muons) {
    // NanoAODv9 (run2_nanoAOD_106Xv1) selection: pt > 3 && at least one standard ID
    if (mu.pt() <= 3) continue;
    if (!mu.passed(reco::Muon::CutBasedIdLoose)        &&
        !mu.passed(reco::Muon::SoftCutBasedId)          &&
        !mu.passed(reco::Muon::SoftMvaId)               &&
        !mu.passed(reco::Muon::CutBasedIdGlobalHighPt)  &&
        !mu.passed(reco::Muon::CutBasedIdTrkHighPt)) continue;
    muon_pt_.push_back(mu.pt());
    muon_eta_.push_back(mu.eta());
    muon_phi_.push_back(mu.phi());
    muon_timeAtIpInOut_.push_back(mu.time().timeAtIpInOut);
    muon_timeNDof_.push_back(mu.time().nDof);
  }

  edm::Handle<std::vector<pat::Electron>> electrons;
  iEvent.getByToken(electronToken_, electrons);
  for (const auto &el : *electrons) {
    if (el.pt() <= 5.0) continue;
    electron_pt_.push_back(el.pt());
    electron_eta_.push_back(el.eta());
    electron_phi_.push_back(el.phi());
  }

  tree_->Fill();
}

DEFINE_FWK_MODULE(MuonTimingAnalyzer);
