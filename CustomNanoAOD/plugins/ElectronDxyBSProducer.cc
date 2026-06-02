// Computes electron beamspot-relative d0 via three independent methods and
// extends the Electron NanoAOD FlatTable with the results.
//
// Background: in MiniAOD produced with CMSSW_9_4_5, PATElectronProducer
// never assigned the beamspot handle to the beamSpot object before calling
// embedHighLevel(), so dB(BS2D) was computed relative to the origin (0,0,0)
// rather than the actual beamspot. This bug was fixed in 2024 (CMSSW commit
// 50e2d9f). All Run 2 MiniAOD is therefore affected.
//
// Columns produced (all in cm):
//   dxybs / dxybsErr             — gsfTrack()->dxy(beamspot), analytic with tilt (primary)
//   dxybs_cached / dxybsErr_cached — cached dB(BS2D) from MiniAOD (wrong for Run 2, kept for verification)
//   dxybs_iptools / dxybsErr_iptools — IPTools::signedTransverseImpactParameter (verification)

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/BeamSpot/interface/BeamSpot.h"
#include "DataFormats/NanoAOD/interface/FlatTable.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/GeometryVector/interface/GlobalVector.h"
#include "TrackingTools/TransientTrack/interface/TransientTrackBuilder.h"
#include "TrackingTools/TransientTrack/interface/TransientTrack.h"
#include "TrackingTools/Records/interface/TransientTrackRecord.h"
#include "TrackingTools/IPTools/interface/IPTools.h"

class ElectronDxyBSProducer : public edm::stream::EDProducer<> {
public:
    explicit ElectronDxyBSProducer(const edm::ParameterSet&);
    void produce(edm::Event&, const edm::EventSetup&) override;

private:
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
    edm::EDGetTokenT<reco::BeamSpot>             beamSpotToken_;
#ifndef CMSSW_LEGACY_NANO_API
    edm::ESGetToken<TransientTrackBuilder, TransientTrackRecord> ttbToken_;
#endif
};

ElectronDxyBSProducer::ElectronDxyBSProducer(const edm::ParameterSet& iConfig)
    : electronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      beamSpotToken_(consumes<reco::BeamSpot>(
          iConfig.getParameter<edm::InputTag>("beamSpot")))
#ifndef CMSSW_LEGACY_NANO_API
    , ttbToken_(esConsumes<TransientTrackBuilder, TransientTrackRecord>(
          edm::ESInputTag("", "TransientTrackBuilder")))
#endif
{
    produces<nanoaod::FlatTable>();
}

void ElectronDxyBSProducer::produce(edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::Electron>> electrons;
    iEvent.getByToken(electronToken_, electrons);

    edm::Handle<reco::BeamSpot> beamSpotHandle;
    iEvent.getByToken(beamSpotToken_, beamSpotHandle);
    const reco::BeamSpot& bs = *beamSpotHandle;

#ifdef CMSSW_LEGACY_NANO_API
    edm::ESHandle<TransientTrackBuilder> ttBuilderHandle;
    iSetup.get<TransientTrackRecord>().get("TransientTrackBuilder", ttBuilderHandle);
    const TransientTrackBuilder& ttBuilder = *ttBuilderHandle;
#else
    const auto& ttBuilder = iSetup.getData(ttbToken_);
#endif

    // Beamspot as a vertex for IPTools; use rotatedCovariance3D to account
    // for tilt in the error (same as PATMuonProducer).
    reco::Vertex vBeamspot(bs.position(), bs.rotatedCovariance3D());

    const size_t n = electrons->size();

    std::vector<float> dxybs(n),          dxybsErr(n);
    std::vector<float> dxybs_cached(n),   dxybsErr_cached(n);
    std::vector<float> dxybs_iptools(n),  dxybsErr_iptools(n);

    for (size_t i = 0; i < n; ++i) {
        const pat::Electron& ele = (*electrons)[i];

        // Verification: cached PAT value — wrong for Run 2 (BS was (0,0,0) in producer)
        dxybs_cached[i]    = ele.dB(pat::Electron::BS2D);
        dxybsErr_cached[i] = ele.edB(pat::Electron::BS2D);  // -1 for all Run 2 data

        auto trk = ele.gsfTrack();
        if (trk.isNonnull()) {
            // Primary: analytic formula with beamspot tilt correction
            dxybs[i]    = trk->dxy(bs);
            dxybsErr[i] = trk->dxyError(bs);

            // Verification: full helix propagation via IPTools
            reco::TransientTrack tt = ttBuilder.build(trk);
            GlobalVector mom(trk->px(), trk->py(), trk->pz());
            auto result = IPTools::signedTransverseImpactParameter(tt, mom, vBeamspot);
            dxybs_iptools[i]    = result.first ? result.second.value() : -999.f;
            dxybsErr_iptools[i] = result.first ? result.second.error() : -999.f;
        } else {
            dxybs[i]          = dxybsErr[i]          = -999.f;
            dxybs_iptools[i]  = dxybsErr_iptools[i]  = -999.f;
        }
    }

    auto table = std::make_unique<nanoaod::FlatTable>(n, "Electron", false, true);

#ifdef CMSSW_LEGACY_NANO_API
    table->addColumn<float>("dxybs",            dxybs,
        "dxy wrt beamspot from gsfTrack()->dxy(beamspot), includes tilt [cm]",
        nanoaod::FlatTable::FloatColumn, 10);
    table->addColumn<float>("dxybsErr",         dxybsErr,
        "dxybs uncertainty from gsfTrack()->dxyError(beamspot) [cm]",
        nanoaod::FlatTable::FloatColumn, 6);
    table->addColumn<float>("dxybs_cached",     dxybs_cached,
        "dxy wrt BS, cached dB(BS2D) [cm]; wrong for Run 2 - computed wrt origin due to CMSSW_9_4_5 bug",
        nanoaod::FlatTable::FloatColumn, 10);
    table->addColumn<float>("dxybsErr_cached",  dxybsErr_cached,
        "dxybs_cached uncertainty [cm]; -1 for all Run 2 data",
        nanoaod::FlatTable::FloatColumn, 6);
    table->addColumn<float>("dxybs_iptools",    dxybs_iptools,
        "dxy wrt BS from IPTools::signedTransverseImpactParameter [cm]; -999 if track or fit invalid",
        nanoaod::FlatTable::FloatColumn, 10);
    table->addColumn<float>("dxybsErr_iptools", dxybsErr_iptools,
        "dxybs_iptools uncertainty [cm]; -999 if track or fit invalid",
        nanoaod::FlatTable::FloatColumn, 6);
#else
    table->addColumn<float>("dxybs",            dxybs,
        "dxy wrt beamspot from gsfTrack()->dxy(beamspot), includes tilt [cm]", 10);
    table->addColumn<float>("dxybsErr",         dxybsErr,
        "dxybs uncertainty from gsfTrack()->dxyError(beamspot) [cm]", 6);
    table->addColumn<float>("dxybs_cached",     dxybs_cached,
        "dxy wrt BS, cached dB(BS2D) [cm]; wrong for Run 2 - computed wrt origin due to CMSSW_9_4_5 bug", 10);
    table->addColumn<float>("dxybsErr_cached",  dxybsErr_cached,
        "dxybs_cached uncertainty [cm]; -1 for all Run 2 data", 6);
    table->addColumn<float>("dxybs_iptools",    dxybs_iptools,
        "dxy wrt BS from IPTools::signedTransverseImpactParameter [cm]; -999 if track or fit invalid", 10);
    table->addColumn<float>("dxybsErr_iptools", dxybsErr_iptools,
        "dxybs_iptools uncertainty [cm]; -999 if track or fit invalid", 6);
#endif

    iEvent.put(std::move(table));
}

DEFINE_FWK_MODULE(ElectronDxyBSProducer);
