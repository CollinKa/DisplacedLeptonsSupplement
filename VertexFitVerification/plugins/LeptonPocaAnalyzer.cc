#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/GeometryVector/interface/GlobalPoint.h"
#include "DataFormats/GeometryVector/interface/GlobalVector.h"
#include "MagneticField/Engine/interface/MagneticField.h"
#include "MagneticField/Records/interface/IdealMagneticFieldRecord.h"
#include "TrackingTools/TrajectoryParametrization/interface/GlobalTrajectoryParameters.h"
#include "TrackingTools/PatternTools/interface/TwoTrackMinimumDistanceHelixHelix.h"
#include "TTree.h"

class LeptonPocaAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
    explicit LeptonPocaAnalyzer(const edm::ParameterSet& cfg);
    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
    void beginJob() override;
    void analyze(const edm::Event& event, const edm::EventSetup& setup) override;
    void endJob() override {}

    void fillPair(const reco::Track& trk1, int pdgId1,
                  const reco::Track& trk2, int pdgId2,
                  const MagneticField* magField);

    edm::EDGetTokenT<std::vector<pat::Muon>> muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
    edm::ESGetToken<MagneticField, IdealMagneticFieldRecord> magFieldToken_;
    double ptCut_;

    TwoTrackMinimumDistanceHelixHelix poca_;
    edm::Service<TFileService> fs_;
    TTree* tree_;

    unsigned int run_, lumi_;
    unsigned long long event_;

    int trk1_pdgId_, trk2_pdgId_;
    float trk1_pt_, trk1_eta_, trk1_phi_, trk1_lambda_, trk1_charge_, trk1_bField_z_;
    float trk1_vx_, trk1_vy_, trk1_vz_;
    float trk2_pt_, trk2_eta_, trk2_phi_, trk2_lambda_, trk2_charge_, trk2_bField_z_;
    float trk2_vx_, trk2_vy_, trk2_vz_;
    float poca1_x_, poca1_y_, poca1_z_;
    float poca2_x_, poca2_y_, poca2_z_;
    int poca_status_;
};

LeptonPocaAnalyzer::LeptonPocaAnalyzer(const edm::ParameterSet& cfg)
    : muonToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>(cfg.getParameter<edm::InputTag>("electrons"))),
      magFieldToken_(esConsumes<MagneticField, IdealMagneticFieldRecord>()),
      ptCut_(cfg.getParameter<double>("ptCut"))
{
    usesResource("TFileService");
}

void LeptonPocaAnalyzer::beginJob() {
    tree_ = fs_->make<TTree>("LeptonPoca", "POCA between lepton pairs");
    tree_->Branch("run",   &run_,   "run/i");
    tree_->Branch("lumi",  &lumi_,  "lumi/i");
    tree_->Branch("event", &event_, "event/l");

    tree_->Branch("trk1_pdgId",   &trk1_pdgId_);
    tree_->Branch("trk1_pt",      &trk1_pt_);
    tree_->Branch("trk1_eta",     &trk1_eta_);
    tree_->Branch("trk1_phi",     &trk1_phi_);
    tree_->Branch("trk1_lambda",  &trk1_lambda_);
    tree_->Branch("trk1_charge",  &trk1_charge_);
    tree_->Branch("trk1_bField_z",&trk1_bField_z_);
    tree_->Branch("trk1_vx",      &trk1_vx_);
    tree_->Branch("trk1_vy",      &trk1_vy_);
    tree_->Branch("trk1_vz",      &trk1_vz_);

    tree_->Branch("trk2_pdgId",   &trk2_pdgId_);
    tree_->Branch("trk2_pt",      &trk2_pt_);
    tree_->Branch("trk2_eta",     &trk2_eta_);
    tree_->Branch("trk2_phi",     &trk2_phi_);
    tree_->Branch("trk2_lambda",  &trk2_lambda_);
    tree_->Branch("trk2_charge",  &trk2_charge_);
    tree_->Branch("trk2_bField_z",&trk2_bField_z_);
    tree_->Branch("trk2_vx",      &trk2_vx_);
    tree_->Branch("trk2_vy",      &trk2_vy_);
    tree_->Branch("trk2_vz",      &trk2_vz_);

    tree_->Branch("poca1_x", &poca1_x_);
    tree_->Branch("poca1_y", &poca1_y_);
    tree_->Branch("poca1_z", &poca1_z_);
    tree_->Branch("poca2_x", &poca2_x_);
    tree_->Branch("poca2_y", &poca2_y_);
    tree_->Branch("poca2_z", &poca2_z_);
    tree_->Branch("poca_status", &poca_status_);
}

void LeptonPocaAnalyzer::analyze(const edm::Event& event, const edm::EventSetup& setup) {
    edm::Handle<std::vector<pat::Muon>> muons;
    event.getByToken(muonToken_, muons);

    edm::Handle<std::vector<pat::Electron>> electrons;
    event.getByToken(electronToken_, electrons);

    const MagneticField* magField = &setup.getData(magFieldToken_);

    run_   = event.id().run();
    lumi_  = event.id().luminosityBlock();
    event_ = event.id().event();

    std::vector<std::pair<const reco::Track*, int>> muTracks, elTracks;

    for (const auto& mu : *muons) {
        if (mu.pt() < ptCut_ || !mu.innerTrack().isNonnull()) continue;
        muTracks.emplace_back(mu.innerTrack().get(), mu.pdgId());
    }
    for (const auto& el : *electrons) {
        if (el.pt() < ptCut_ || !el.gsfTrack().isNonnull()) continue;
        elTracks.emplace_back(el.gsfTrack().get(), el.pdgId());
    }

    for (size_t i = 0; i < muTracks.size(); ++i)
        for (size_t j = i + 1; j < muTracks.size(); ++j)
            fillPair(*muTracks[i].first, muTracks[i].second,
                     *muTracks[j].first, muTracks[j].second, magField);

    for (const auto& [trk1, id1] : muTracks)
        for (const auto& [trk2, id2] : elTracks)
            fillPair(*trk1, id1, *trk2, id2, magField);

    for (size_t i = 0; i < elTracks.size(); ++i)
        for (size_t j = i + 1; j < elTracks.size(); ++j)
            fillPair(*elTracks[i].first, elTracks[i].second,
                     *elTracks[j].first, elTracks[j].second, magField);
}

void LeptonPocaAnalyzer::fillPair(const reco::Track& trk1, int pdgId1,
                                   const reco::Track& trk2, int pdgId2,
                                   const MagneticField* magField) {
    GlobalPoint pos1(trk1.vx(), trk1.vy(), trk1.vz());
    GlobalPoint pos2(trk2.vx(), trk2.vy(), trk2.vz());
    GlobalVector mom1(trk1.px(), trk1.py(), trk1.pz());
    GlobalVector mom2(trk2.px(), trk2.py(), trk2.pz());

    GlobalTrajectoryParameters gtp1(pos1, mom1, trk1.charge(), magField);
    GlobalTrajectoryParameters gtp2(pos2, mom2, trk2.charge(), magField);

    poca_status_ = poca_.calculate(gtp1, gtp2) ? 1 : 0;

    auto [pt1, pt2] = poca_.points();  // (pointG, pointH) = (trk1 point, trk2 point)

    trk1_pdgId_   = pdgId1;
    trk1_pt_      = trk1.pt();
    trk1_eta_     = trk1.eta();
    trk1_phi_     = trk1.phi();
    trk1_lambda_  = trk1.lambda();
    trk1_charge_  = trk1.charge();
    trk1_bField_z_= magField->inInverseGeV(pos1).z();
    trk1_vx_      = trk1.vx();
    trk1_vy_      = trk1.vy();
    trk1_vz_      = trk1.vz();

    trk2_pdgId_   = pdgId2;
    trk2_pt_      = trk2.pt();
    trk2_eta_     = trk2.eta();
    trk2_phi_     = trk2.phi();
    trk2_lambda_  = trk2.lambda();
    trk2_charge_  = trk2.charge();
    trk2_bField_z_= magField->inInverseGeV(pos2).z();
    trk2_vx_      = trk2.vx();
    trk2_vy_      = trk2.vy();
    trk2_vz_      = trk2.vz();

    poca1_x_ = pt1.x();  poca1_y_ = pt1.y();  poca1_z_ = pt1.z();
    poca2_x_ = pt2.x();  poca2_y_ = pt2.y();  poca2_z_ = pt2.z();

    tree_->Fill();
}

void LeptonPocaAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("muons",     edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<double>("ptCut", 5.0);
    descriptions.addDefault(desc);
}

DEFINE_FWK_MODULE(LeptonPocaAnalyzer);
