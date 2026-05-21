// Fits all dilepton pairs with KalmanVertexFitter and writes pairs that
// converge (chi2/ndof < 20) and land in tracker material to a FlatTable.
// Output collection: InMaterialVtx_{lep1Idx, lep2Idx, lep1Flavor, lep2Flavor}
// Flavor encoding: 0 = muon (index into Muon table), 1 = electron (index into Electron table)
// For eμ pairs, lep1 is always the muon and lep2 is always the electron.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/NanoAOD/interface/FlatTable.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "TrackingTools/TransientTrack/interface/TransientTrackBuilder.h"
#include "TrackingTools/TransientTrack/interface/TransientTrack.h"
#include "TrackingTools/Records/interface/TransientTrackRecord.h"
#include "RecoVertex/KalmanVertexFit/interface/KalmanVertexFitter.h"
#include "RecoVertex/VertexPrimitives/interface/TransientVertex.h"

#include <cmath>
#include <cstdint>
#include <vector>

// Phase 1 pixel detector material geometry (all dimensions in cm).
// Each volume is expanded by 10 µm in each direction to account for vertex
// position resolution, following the Run 2 DisplacedSUSY analysis convention.
// Beam center offsets are from 2018 (CMSSW_10_2_x alignment).
// TODO: update beam center values for Run 3 alignment per year.
namespace {

// beam pipe
constexpr double kBeamPipeXCenter  =  0.171;
constexpr double kBeamPipeYCenter  = -0.176;
constexpr double kBeamPipeInnerR   =  2.170;
constexpr double kBeamPipeOuterR   =  2.251;

// BPIX inner shield (two offset half-cylinders)
constexpr double kNearShieldXCenter = -0.093;
constexpr double kNearShieldYCenter = -0.091;
constexpr double kFarShieldXCenter  =  0.044;
constexpr double kFarShieldYCenter  = -0.098;
constexpr double kInnerShieldInnerR =  2.360;
constexpr double kInnerShieldOuterR =  2.441;

// BPIX barrel layers (L1–L4)
constexpr double kBpixXCenter   =  0.0856367;
constexpr double kBpixYCenter   = -0.101882;
constexpr double kBpixZCenter   = -0.326049;
constexpr double kBpixZHalfLen  = 27.4505;
constexpr double kBpixL1InnerR  =  2.725;
constexpr double kBpixL1OuterR  =  3.176;
constexpr double kBpixL2InnerR  =  6.525;
constexpr double kBpixL2OuterR  =  7.076;
constexpr double kBpixL3InnerR  = 10.825;
constexpr double kBpixL3OuterR  = 10.976;
constexpr double kBpixL4InnerR  = 15.925;
constexpr double kBpixL4OuterR  = 16.076;

// FPIX forward disks (D1–D3, both ±z sides)
constexpr double kFpixXCenter    =  0.0311191;
constexpr double kFpixYCenter    = -0.106233;
constexpr double kFpixZCenter    = -0.338382;
constexpr double kFpixInnerR     =  4.500;
constexpr double kFpixOuterR     = 16.101;
constexpr double kFpixZHalfThick =  0.0755;
constexpr double kFpixD1ZCenter  = 29.1;
constexpr double kFpixD2ZCenter  = 39.6;
constexpr double kFpixD3ZCenter  = 51.6;

// pixel support tube
constexpr double kTubeXCenter  = -0.080;
constexpr double kTubeYCenter  = -0.320;
constexpr double kTubeInnerRX  = 21.625;
constexpr double kTubeInnerRY  = 21.725;
constexpr double kTubeOuterRX  = 21.776;
constexpr double kTubeOuterRY  = 21.876;

bool inCircle(double cx, double cy, double r, double x, double y) {
    double dx = x - cx, dy = y - cy;
    return dx*dx + dy*dy < r*r;
}

bool inEllipse(double cx, double cy, double rx, double ry, double x, double y) {
    double dx = x - cx, dy = y - cy;
    return dx*dx/(rx*rx) + dy*dy/(ry*ry) < 1.0;
}

bool inMaterial(double vx, double vy, double vz) {
    // beam pipe
    if (inCircle(kBeamPipeXCenter, kBeamPipeYCenter, kBeamPipeOuterR, vx, vy) &&
        !inCircle(kBeamPipeXCenter, kBeamPipeYCenter, kBeamPipeInnerR, vx, vy))
        return true;

    bool inBpixZ = vz > kBpixZCenter - kBpixZHalfLen &&
                   vz < kBpixZCenter + kBpixZHalfLen;

    // BPIX inner shield
    if (inBpixZ) {
        bool nearSide = vx > 0.0 &&
            inCircle(kNearShieldXCenter, kNearShieldYCenter, kInnerShieldOuterR, vx, vy) &&
            !inCircle(kNearShieldXCenter, kNearShieldYCenter, kInnerShieldInnerR, vx, vy);
        bool farSide = vx <= 0.0 &&
            inCircle(kFarShieldXCenter, kFarShieldYCenter, kInnerShieldOuterR, vx, vy) &&
            !inCircle(kFarShieldXCenter, kFarShieldYCenter, kInnerShieldInnerR, vx, vy);
        if (nearSide || farSide) return true;
    }

    // BPIX barrel layers
    if (inBpixZ) {
        bool inL1 = inCircle(kBpixXCenter, kBpixYCenter, kBpixL1OuterR, vx, vy) &&
                    !inCircle(kBpixXCenter, kBpixYCenter, kBpixL1InnerR, vx, vy);
        bool inL2 = inCircle(kBpixXCenter, kBpixYCenter, kBpixL2OuterR, vx, vy) &&
                    !inCircle(kBpixXCenter, kBpixYCenter, kBpixL2InnerR, vx, vy);
        bool inL3 = inCircle(kBpixXCenter, kBpixYCenter, kBpixL3OuterR, vx, vy) &&
                    !inCircle(kBpixXCenter, kBpixYCenter, kBpixL3InnerR, vx, vy);
        bool inL4 = inCircle(kBpixXCenter, kBpixYCenter, kBpixL4OuterR, vx, vy) &&
                    !inCircle(kBpixXCenter, kBpixYCenter, kBpixL4InnerR, vx, vy);
        if (inL1 || inL2 || inL3 || inL4) return true;
    }

    // FPIX forward disks
    bool inFpixR = inCircle(kFpixXCenter, kFpixYCenter, kFpixOuterR, vx, vy) &&
                   !inCircle(kFpixXCenter, kFpixYCenter, kFpixInnerR, vx, vy);
    if (inFpixR) {
        auto inDisk = [&](double dz) {
            return (vz > kFpixZCenter + dz - kFpixZHalfThick &&
                    vz < kFpixZCenter + dz + kFpixZHalfThick) ||
                   (vz > kFpixZCenter - dz - kFpixZHalfThick &&
                    vz < kFpixZCenter - dz + kFpixZHalfThick);
        };
        if (inDisk(kFpixD1ZCenter) || inDisk(kFpixD2ZCenter) || inDisk(kFpixD3ZCenter))
            return true;
    }

    // pixel support tube
    if (inEllipse(kTubeXCenter, kTubeYCenter, kTubeOuterRX, kTubeOuterRY, vx, vy) &&
        !inEllipse(kTubeXCenter, kTubeYCenter, kTubeInnerRX, kTubeInnerRY, vx, vy))
        return true;

    return false;
}

} // namespace

class InMaterialVertexTableProducer : public edm::stream::EDProducer<> {
public:
    explicit InMaterialVertexTableProducer(const edm::ParameterSet& iConfig)
        : muonToken_(consumes<std::vector<pat::Muon>>(
              iConfig.getParameter<edm::InputTag>("muons"))),
          electronToken_(consumes<std::vector<pat::Electron>>(
              iConfig.getParameter<edm::InputTag>("electrons")))
#ifndef CMSSW_LEGACY_NANO_API
        , ttbToken_(esConsumes<TransientTrackBuilder, TransientTrackRecord>(
              edm::ESInputTag("", "TransientTrackBuilder")))
#endif
    {
        produces<nanoaod::FlatTable>();
    }

    void produce(edm::Event& iEvent, const edm::EventSetup& iSetup) override {
        edm::Handle<std::vector<pat::Muon>> muons;
        iEvent.getByToken(muonToken_, muons);

        edm::Handle<std::vector<pat::Electron>> electrons;
        iEvent.getByToken(electronToken_, electrons);

#ifdef CMSSW_LEGACY_NANO_API
        edm::ESHandle<TransientTrackBuilder> ttBuilderHandle;
        iSetup.get<TransientTrackRecord>().get("TransientTrackBuilder", ttBuilderHandle);
        const TransientTrackBuilder& ttBuilder = *ttBuilderHandle;
#else
        const auto& ttBuilder = iSetup.getData(ttbToken_);
#endif
        KalmanVertexFitter kvf;

        std::vector<int16_t> lep1Idx, lep2Idx;
        std::vector<uint8_t> lep1Flavor, lep2Flavor;

        auto tryFit = [&](const reco::TransientTrack& tt1, const reco::TransientTrack& tt2,
                          int16_t i1, uint8_t f1, int16_t i2, uint8_t f2) {
            std::vector<reco::TransientTrack> tts = {tt1, tt2};
            TransientVertex tv = kvf.vertex(tts);
            if (!tv.isValid()) return;
            reco::Vertex vtx(tv);
            if (vtx.normalizedChi2() >= 20.0) return;
            if (!inMaterial(vtx.x(), vtx.y(), vtx.z())) return;
            lep1Idx.push_back(i1);
            lep2Idx.push_back(i2);
            lep1Flavor.push_back(f1);
            lep2Flavor.push_back(f2);
        };

        // Build transient tracks for leptons with valid tracks
        std::vector<std::pair<reco::TransientTrack, int16_t>> muTTs, elTTs;
        for (int16_t i = 0; i < static_cast<int16_t>(muons->size()); ++i) {
            const auto& mu = (*muons)[i];
            if (mu.innerTrack().isNonnull())
                muTTs.emplace_back(ttBuilder.build(mu.innerTrack()), i);
        }
        for (int16_t i = 0; i < static_cast<int16_t>(electrons->size()); ++i) {
            const auto& el = (*electrons)[i];
            if (el.gsfTrack().isNonnull())
                elTTs.emplace_back(ttBuilder.build(el.gsfTrack()), i);
        }

        // μμ pairs
        for (size_t i = 0; i < muTTs.size(); ++i)
            for (size_t j = i + 1; j < muTTs.size(); ++j)
                tryFit(muTTs[i].first, muTTs[j].first,
                       muTTs[i].second, 0, muTTs[j].second, 0);

        // ee pairs
        for (size_t i = 0; i < elTTs.size(); ++i)
            for (size_t j = i + 1; j < elTTs.size(); ++j)
                tryFit(elTTs[i].first, elTTs[j].first,
                       elTTs[i].second, 1, elTTs[j].second, 1);

        // eμ pairs (lep1=muon, lep2=electron)
        for (auto& [muTT, muIdx] : muTTs)
            for (auto& [elTT, elIdx] : elTTs)
                tryFit(muTT, elTT, muIdx, 0, elIdx, 1);

        auto table = std::make_unique<nanoaod::FlatTable>(lep1Idx.size(), "InMaterialVtx", false, false);
#ifdef CMSSW_LEGACY_NANO_API
        // CMSSW 10_2_x: explicit template type and ColumnType required; Int16 may be absent so use int.
        std::vector<int> lep1Idx_i(lep1Idx.begin(), lep1Idx.end());
        std::vector<int> lep2Idx_i(lep2Idx.begin(), lep2Idx.end());
        table->addColumn<int>("lep1Idx", lep1Idx_i,
            "index of first lepton into Muon (lep1Flavor=0) or Electron (lep1Flavor=1) table",
            nanoaod::FlatTable::IntColumn);
        table->addColumn<int>("lep2Idx", lep2Idx_i,
            "index of second lepton into Muon (lep2Flavor=0) or Electron (lep2Flavor=1) table",
            nanoaod::FlatTable::IntColumn);
        table->addColumn<uint8_t>("lep1Flavor", lep1Flavor,
            "flavor of first lepton: 0=muon, 1=electron; for eμ pairs lep1 is always the muon",
            nanoaod::FlatTable::UInt8Column);
        table->addColumn<uint8_t>("lep2Flavor", lep2Flavor,
            "flavor of second lepton: 0=muon, 1=electron; for eμ pairs lep2 is always the electron",
            nanoaod::FlatTable::UInt8Column);
#else
        table->addColumn<int16_t>("lep1Idx",    lep1Idx,
            "index of first lepton into Muon (lep1Flavor=0) or Electron (lep1Flavor=1) table");
        table->addColumn<int16_t>("lep2Idx",    lep2Idx,
            "index of second lepton into Muon (lep2Flavor=0) or Electron (lep2Flavor=1) table");
        table->addColumn<uint8_t>("lep1Flavor", lep1Flavor,
            "flavor of first lepton: 0=muon, 1=electron; for eμ pairs lep1 is always the muon");
        table->addColumn<uint8_t>("lep2Flavor", lep2Flavor,
            "flavor of second lepton: 0=muon, 1=electron; for eμ pairs lep2 is always the electron");
#endif
        iEvent.put(std::move(table));
    }

private:
    edm::EDGetTokenT<std::vector<pat::Muon>>     muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
#ifndef CMSSW_LEGACY_NANO_API
    edm::ESGetToken<TransientTrackBuilder, TransientTrackRecord> ttbToken_;
#endif
};

DEFINE_FWK_MODULE(InMaterialVertexTableProducer);
