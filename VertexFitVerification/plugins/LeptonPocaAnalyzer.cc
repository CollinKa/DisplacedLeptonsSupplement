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
#include <algorithm>
#include <cmath>

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

    // Stub for the instrumented custom implementation — delegates to poca_ for now.
    bool customCalculate(const GlobalTrajectoryParameters& gtp1,
                         const GlobalTrajectoryParameters& gtp2,
                         GlobalPoint& pt1, GlobalPoint& pt2);

    edm::EDGetTokenT<std::vector<pat::Muon>> muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
    edm::ESGetToken<MagneticField, IdealMagneticFieldRecord> magFieldToken_;
    double ptCut_;
    bool useCustomPoca_;

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

    // Debug branches from custom POCA — only filled when useCustomPoca_ is true
    float coeff_a_, coeff_b_;
    float coeff_c1_, coeff_c2_;
    float coeff_d1_, coeff_d2_;
    float coeff_e1_, coeff_e2_;
    int   n_iter_;
    float dphi_trk1_[6];   // delta phi for G (trk1) at each iteration
    float dphi_trk2_[6];   // delta phi for H (trk2) at each iteration
};

LeptonPocaAnalyzer::LeptonPocaAnalyzer(const edm::ParameterSet& cfg)
    : muonToken_(consumes<std::vector<pat::Muon>>(cfg.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>(cfg.getParameter<edm::InputTag>("electrons"))),
      magFieldToken_(esConsumes<MagneticField, IdealMagneticFieldRecord>()),
      ptCut_(cfg.getParameter<double>("ptCut")),
      useCustomPoca_(cfg.getParameter<bool>("useCustomPoca"))
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

    tree_->Branch("coeff_a",  &coeff_a_);
    tree_->Branch("coeff_b",  &coeff_b_);
    tree_->Branch("coeff_c1", &coeff_c1_);
    tree_->Branch("coeff_c2", &coeff_c2_);
    tree_->Branch("coeff_d1", &coeff_d1_);
    tree_->Branch("coeff_d2", &coeff_d2_);
    tree_->Branch("coeff_e1", &coeff_e1_);
    tree_->Branch("coeff_e2", &coeff_e2_);
    tree_->Branch("n_iter",    &n_iter_);
    tree_->Branch("dphi_trk1", dphi_trk1_, "dphi_trk1[6]/F");
    tree_->Branch("dphi_trk2", dphi_trk2_, "dphi_trk2[6]/F");
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

    coeff_a_ = coeff_b_ = 0.f;
    coeff_c1_ = coeff_c2_ = 0.f;
    coeff_d1_ = coeff_d2_ = 0.f;
    coeff_e1_ = coeff_e2_ = 0.f;
    n_iter_ = 0;
    std::fill(dphi_trk1_, dphi_trk1_ + 6, 0.f);
    std::fill(dphi_trk2_, dphi_trk2_ + 6, 0.f);

    GlobalPoint pt1, pt2;
    if (useCustomPoca_) {
        poca_status_ = customCalculate(gtp1, gtp2, pt1, pt2) ? 1 : 0;
    } else {
        poca_status_ = poca_.calculate(gtp1, gtp2) ? 1 : 0;
        auto [p1, p2] = poca_.points();
        pt1 = p1;  pt2 = p2;
    }

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

bool LeptonPocaAnalyzer::customCalculate(const GlobalTrajectoryParameters& gtp1,
                                          const GlobalTrajectoryParameters& gtp2,
                                          GlobalPoint& pt1, GlobalPoint& pt2) {
    // Convention: G = gtp1 (trk1), H = gtp2 (trk2), matching calculate(G, H) in
    // TwoTrackMinimumDistanceHelixHelix.  Variable names follow that class directly.
    const double Bc2kG = gtp1.magneticField().inInverseGeV(gtp1.position()).z();
    const double Bc2kH = gtp2.magneticField().inInverseGeV(gtp2.position()).z();
    const double Gt = gtp1.momentum().perp();
    const double Ht = gtp2.momentum().perp();

    const double theg = Gt / (gtp1.charge() * Bc2kG);
    const double theh = Ht / (gtp2.charge() * Bc2kH);

    const double sinpG0     = -gtp1.momentum().y() / Gt;
    const double cospG0     = -gtp1.momentum().x() / Gt;
    const double tanlambdaG = -gtp1.momentum().z() / Gt;
    const double pG0        = std::atan2(sinpG0, cospG0);

    const double sinpH0     = -gtp2.momentum().y() / Ht;
    const double cospH0     = -gtp2.momentum().x() / Ht;
    const double tanlambdaH = -gtp2.momentum().z() / Ht;
    const double pH0        = std::atan2(sinpH0, cospH0);

    const double dz = gtp2.position().z() - gtp1.position().z()
                      - theh * pH0 * tanlambdaH + theg * pG0 * tanlambdaG;

    coeff_a_  = gtp2.position().x() - gtp1.position().x() + theg * sinpG0 - theh * sinpH0;
    coeff_b_  = gtp2.position().y() - gtp1.position().y() - theg * cospG0 + theh * cospH0;
    coeff_c1_ = theh * tanlambdaH * tanlambdaH;
    coeff_c2_ = -theg * tanlambdaG * tanlambdaG;
    coeff_d1_ = -theg * tanlambdaG * tanlambdaH;
    coeff_d2_ = theh * tanlambdaG * tanlambdaH;
    coeff_e1_ = tanlambdaH * dz;
    coeff_e2_ = tanlambdaG * dz;

    // Newton-Kantorowitsch iteration — mirrors calculate() + oneIteration() in
    // TwoTrackMinimumDistanceHelixHelix.  Constants match that class's constructor defaults.
    static const double qual     = 0.001;
    static const double maxjump  = 20.;
    static const double singjacI = 1. / 0.1;
    static const int    maxiter  = 4;

    double curpG = pG0, curpH = pH0;
    bool retval = false;
    double dG = 0., dH = 0.;

    for (int iter = 0; ; ++iter) {
        const double sinG = std::sin(curpG), cosG = std::cos(curpG);
        const double sinH = std::sin(curpH), cosH = std::cos(curpH);

        const double A11 = theh * (-sinH * (coeff_a_ - theg * sinG) + cosH * (coeff_b_ + theg * cosG) + coeff_c1_);
        if (A11 < 0.) { retval = true; break; }
        const double A22 = -theg * (-sinG * (coeff_a_ + theh * sinH) + cosG * (coeff_b_ - theh * cosH) + coeff_c2_);
        if (A22 < 0.) { retval = true; break; }

        const double A12   = theh * (-theg * cosG * cosH - theg * sinH * sinG + coeff_d1_);
        const double A21   = -theg * (theh * cosG * cosH + theh * sinH * sinG + coeff_d2_);
        const double detaI = 1. / (A11 * A22 - A12 * A21);

        const double z1 = theh * (cosH * (coeff_a_ - theg * sinG) + sinH * (coeff_b_ + theg * cosG)
                                  + coeff_c1_ * curpH + coeff_d1_ * curpG + coeff_e1_);
        const double z2 = -theg * (cosG * (coeff_a_ + theh * sinH) + sinG * (coeff_b_ - theh * cosH)
                                   + coeff_c2_ * curpG + coeff_d2_ * curpH + coeff_e2_);

        dH = (z1 * A22 - z2 * A12) * detaI;
        dG = (z2 * A11 - z1 * A21) * detaI;

        // Save delta phis before any early-exit checks, so the array always reflects
        // what was computed even when the iteration fails.
        if (n_iter_ < 6) {
            dphi_trk1_[n_iter_] = static_cast<float>(dG);
            dphi_trk2_[n_iter_] = static_cast<float>(dH);
        }
        ++n_iter_;

        if (!std::isfinite(dH) || !std::isfinite(dG)) { retval = true; break; }
        if (std::fabs(detaI) > singjacI)               { retval = true; break; }

        curpH -= dH;
        curpG -= dG;

        if (iter > maxiter)                                        { retval = true; break; }
        if (std::fabs(dH) <= qual && std::fabs(dG) <= qual) break;
    }

    if (std::fabs(theg * (curpG - pG0)) > maxjump) retval = true;
    if (std::fabs(theh * (curpH - pH0)) > maxjump) retval = true;

    // finalPoints
    pt1 = GlobalPoint(
        gtp1.position().x() + theg * (std::sin(curpG) - sinpG0),
        gtp1.position().y() + theg * (-std::cos(curpG) + cospG0),
        gtp1.position().z() + theg * tanlambdaG * (curpG - pG0)
    );
    pt2 = GlobalPoint(
        gtp2.position().x() + theh * (std::sin(curpH) - sinpH0),
        gtp2.position().y() + theh * (-std::cos(curpH) + cospH0),
        gtp2.position().z() + theh * tanlambdaH * (curpH - pH0)
    );

    return retval;
}

void LeptonPocaAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("muons",     edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<double>("ptCut", 5.0);
    desc.add<bool>("useCustomPoca", false);
    descriptions.addDefault(desc);
}

DEFINE_FWK_MODULE(LeptonPocaAnalyzer);
